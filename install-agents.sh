#!/usr/bin/env bash
# Bash 3.2+; writes need a SHA-256 utility, and remote reads also need curl.
set -euo pipefail
IFS=$'\n\t'

REPOSITORY='crankyjediii/claude-code-subagents'
REF='main'
SOURCE=''
TARGET=''
CLIENT='claude'
SCOPE=''
PROJECT=''
EXT='md'
ACTION='interactive'
SELECTION=''
CATEGORY=''
ALL=0
FORCE=0
DRY_RUN=0
REMOTE=0
TEMP_DIR=''
BACKUP_DIR=''
CATALOG=''
LOCK_DIR=''
LOCK_HELD=0
STAGED_FILE=''
STAGED_STATE=''
NAMES=()
PATHS=()
HASHES=()
CATEGORIES=()
SELECTED=()

usage() {
    cat <<'USAGE'
Usage: bash install-agents.sh [ACTION] [OPTIONS]

With no action, open the interactive category browser.

Actions:
  --list                       List the catalog (optionally filter by category)
  --installed                  List files managed in the selected target
  --install NAME[,NAME...]      Install selected agents
  --uninstall NAME[,NAME...]    Remove selected managed agents
  --install --all               Install all agents
  --uninstall --all             Remove all managed agents
  --install --category SLUG     Install one category (folder or plugin name)

Targets (default: selected client agents directory in the current directory):
  --client NAME                claude (default), codex, cursor, or opencode
  --global                     Use the selected client's user agents directory
  --project DIRECTORY          Use the selected client under DIRECTORY
  --target DIRECTORY           Use an explicit agents directory

Sources:
  --local DIRECTORY            Use a local repository without network access
  --standalone                 Fetch from GitHub even beside a local clone
  --repo OWNER/REPOSITORY       GitHub repository to fetch
  --ref REF                    Branch, tag, or commit (see default source below)

Other options:
  --force                      Back up and replace/remove conflicting files
  --dry-run                    Show actions without changing the target
  --help                       Show this help

Explicit install/uninstall commands execute without an extra prompt.
Remote operations require curl and sha256sum or shasum. Pin --ref to a commit
for repeatable downloads. --force never follows file or state symlinks.
USAGE
    printf '\nDefault source: %s@%s\n' "$REPOSITORY" "$REF"
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*" >&2; }
cleanup() {
    if [[ -n "$STAGED_FILE" ]]; then rm -f -- "$STAGED_FILE"; fi
    if [[ -n "$STAGED_STATE" ]]; then rm -f -- "$STAGED_STATE"; fi
    if [[ "$LOCK_HELD" == 1 ]]; then
        rm -f -- "$LOCK_DIR/pid"
        rmdir -- "$LOCK_DIR" || log "Could not remove installer lock: $LOCK_DIR"
    fi
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then rm -rf -- "$TEMP_DIR"; fi
}
need_value() { [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || die "Missing value for $1"; }
valid_name() { [[ "$1" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; }
set_action() {
    [[ "$ACTION" == interactive ]] || die 'Choose exactly one action.'
    ACTION="$1"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h) usage; exit 0 ;;
            --list) set_action list; shift ;;
            --installed) set_action installed; shift ;;
            --install|--uninstall)
                set_action "${1#--}"; shift
                if [[ $# -gt 0 && "$1" != --* ]]; then SELECTION="$1"; shift; fi ;;
            --global) [[ -z "$TARGET" ]] || die 'Choose one target.'; SCOPE=global; TARGET='scope'; shift ;;
            --project) need_value "$@"; [[ -z "$TARGET" ]] || die 'Choose one target.'; SCOPE=project; PROJECT="$2"; TARGET=scope; shift 2 ;;
            --target) need_value "$@"; [[ -z "$TARGET" ]] || die 'Choose one target.'; TARGET="$2"; shift 2 ;;
            --client) need_value "$@"; CLIENT="$2"; shift 2 ;;
            --local) need_value "$@"; SOURCE="$2"; shift 2 ;;
            --standalone) REMOTE=1; shift ;;
            --repo) need_value "$@"; REPOSITORY="$2"; REMOTE=1; shift 2 ;;
            --ref) need_value "$@"; REF="$2"; shift 2 ;;
            --category) need_value "$@"; CATEGORY="$2"; shift 2 ;;
            --all) ALL=1; shift ;;
            --force) FORCE=1; shift ;;
            --dry-run) DRY_RUN=1; shift ;;
            *) die "Unknown argument: $1 (see --help)" ;;
        esac
    done
    case "$CLIENT" in
        claude|cursor|opencode) EXT=md ;;
        codex) EXT=toml ;;
        *) die "Unknown client: $CLIENT (choose claude, codex, cursor, opencode)" ;;
    esac
    if [[ -n "$SCOPE" ]]; then TARGET=$(client_target "$SCOPE" "${PROJECT:-$PWD}"); fi
    [[ "$REPOSITORY" =~ ^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+$ && "${REPOSITORY#*/}" != . && "${REPOSITORY#*/}" != .. ]] || die 'Invalid GitHub repository.'
    [[ "$REF" =~ ^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$ && "$REF" != *..* && "$REF" != . && "$REF" != ./* && "$REF" != */./* && "$REF" != */. ]] || die 'Invalid ref.'
    if [[ -n "$SELECTION" ]]; then
        [[ "$SELECTION" =~ ^[a-z0-9]+(-[a-z0-9]+)*(,[a-z0-9]+(-[a-z0-9]+)*)*$ ]] || die 'Invalid agent selection; use comma-separated names on one line.'
    fi
    [[ -z "$SOURCE" || "$REMOTE" == 0 ]] || die 'Choose --local or a remote source.'
    if [[ -n "$CATEGORY" ]]; then valid_name "$CATEGORY" || die 'Invalid category.'; fi
    local selectors=0
    [[ -z "$SELECTION" ]] || selectors=$((selectors + 1))
    [[ -z "$CATEGORY" ]] || selectors=$((selectors + 1))
    [[ "$ALL" == 0 ]] || selectors=$((selectors + 1))
    [[ "$selectors" -le 1 ]] || die 'Choose names, --category, or --all.'
    case "$ACTION" in
        install|uninstall) [[ "$selectors" == 1 ]] || die 'Select names, --category, or --all.' ;;
        list) [[ -z "$SELECTION" && "$ALL" == 0 ]] || die '--list accepts only --category.' ;;
        installed) [[ "$selectors" == 0 ]] || die '--installed does not accept selectors.' ;;
        interactive) [[ "$selectors" == 0 ]] || die 'Selectors require --install, --uninstall, or --list.' ;;
    esac
}

client_target() {
    local scope="$1" project="$2"
    if [[ "$scope" == global ]]; then
        case "$CLIENT" in
            codex) printf '%s/agents\n' "${CODEX_HOME:-$HOME/.codex}" ;;
            opencode) printf '%s/opencode/agents\n' "${XDG_CONFIG_HOME:-$HOME/.config}" ;;
            *) printf '%s/.%s/agents\n' "$HOME" "$CLIENT" ;;
        esac
    else
        printf '%s/.%s/agents\n' "$project" "$CLIENT"
    fi
}

render_agent() {
    [[ "$CLIENT" != claude ]] || return 0
    command -v python3 >/dev/null 2>&1 || die 'Non-Claude formats require Python 3.'
    python3 - "$CLIENT" "$1" <<'PYTHON'
import json
import pathlib
import sys
client, filename = sys.argv[1:]
path = pathlib.Path(filename)
text = path.read_text(encoding="utf-8")
_, header, body = text.split("---", 2)
metadata = dict(line.split(":", 1) for line in header.strip().splitlines())
name = metadata["name"].strip()
description = metadata["description"].strip()
# The collection uses JSON-compatible quoted YAML descriptions.
if description.startswith('"'):
    description = json.loads(description)
body = body.lstrip("\n")
quote = lambda value: json.dumps(value, ensure_ascii=False)
if client == "codex":
    output = "".join(f"{key} = {quote(value)}\n" for key, value in (
        ("name", name), ("description", description), ("developer_instructions", body)))
else:
    extra = "mode: subagent\n" if client == "opencode" else ""
    output = f"---\nname: {name}\ndescription: {quote(description)}\n{extra}---\n\n{body}"
path.write_text(output, encoding="utf-8")
PYTHON
}

hash_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -- "$1" | cut -d ' ' -f 1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -- "$1" | cut -d ' ' -f 1
    else
        die 'Install sha256sum or shasum to verify agent files.'
    fi
}

fetch() {
    local relative="$1" output="$2"
    if [[ -n "$SOURCE" ]]; then
        [[ -f "$SOURCE/$relative" && ! -L "$SOURCE/$relative" ]] || die "Missing or symlinked source: $relative"
        cp -- "$SOURCE/$relative" "$output" || die "Could not read $relative"
    else
        command -v curl >/dev/null 2>&1 || die 'Standalone mode requires curl.'
        curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
            --connect-timeout 15 --max-time 120 --retry 2 \
            "https://raw.githubusercontent.com/$REPOSITORY/$REF/$relative" -o "$output" || die "Download failed: $relative"
    fi
}

load_catalog() {
    CATALOG="$TEMP_DIR/catalog.tsv"
    fetch tools/catalog.tsv "$CATALOG"
    local category plugin name description relative digest extra
    while IFS='|' read -r category plugin name description relative digest extra || [[ -n "$category" ]]; do
        [[ -n "$category" ]] || continue
        [[ "$category" =~ ^[0-9][0-9]-[a-z0-9-]+$ ]] || die 'Invalid catalog category.'
        if ! valid_name "$name" || ! valid_name "$plugin"; then die 'Invalid catalog name.'; fi
        [[ -n "$description" && -z "$extra" && "$digest" =~ ^[a-f0-9]{64}$ ]] || die 'Invalid catalog record.'
        [[ "$relative" == "categories/$category/agents/$name.md" ]] || die 'Unsafe catalog path.'
        local prior
        for prior in "${NAMES[@]+"${NAMES[@]}"}"; do [[ "$prior" != "$name" ]] || die "Duplicate catalog name: $name"; done
        NAMES+=("$name"); PATHS+=("$relative"); HASHES+=("$digest"); CATEGORIES+=("$category|$plugin|$description")
    done < "$CATALOG"
    [[ ${#NAMES[@]} -gt 0 ]] || die 'The catalog is empty.'
}

show_catalog() {
    local i cat plugin description found=0
    for ((i=0; i<${#NAMES[@]}; i++)); do
        IFS='|' read -r cat plugin description <<< "${CATEGORIES[$i]}"
        if [[ -z "$CATEGORY" || "$CATEGORY" == "$cat" || "$CATEGORY" == "$plugin" ]]; then
            printf '%-32s %-27s %s\n' "${NAMES[$i]}" "$plugin" "$description"
            found=1
        fi
    done
    [[ "$found" == 1 ]] || die "Unknown category: $CATEGORY"
}

choose_agents() {
    local i cat plugin ignored wanted seen
    if [[ -n "$SELECTION" ]]; then
        [[ "$SELECTION" =~ ^[a-z0-9]+(-[a-z0-9]+)*(,[a-z0-9]+(-[a-z0-9]+)*)*$ ]] || die 'Invalid agent selection; use comma-separated names on one line.'
        local requested=()
        IFS=',' read -r -a requested <<< "$SELECTION"
        for wanted in "${requested[@]}"; do
            valid_name "$wanted" || die "Invalid agent name: $wanted"
            seen=0
            for ignored in "${SELECTED[@]+"${SELECTED[@]}"}"; do
                [[ "${NAMES[$ignored]}" != "$wanted" ]] || seen=1
            done
            [[ "$seen" == 0 ]] || continue
            seen=0
            for ((i=0; i<${#NAMES[@]}; i++)); do
                if [[ "${NAMES[$i]}" == "$wanted" ]]; then SELECTED+=("$i"); seen=1; break; fi
            done
            [[ "$seen" == 1 ]] || die "Unknown agent: $wanted"
        done
    else
        for ((i=0; i<${#NAMES[@]}; i++)); do
            IFS='|' read -r cat plugin ignored <<< "${CATEGORIES[$i]}"
            if [[ "$ALL" == 1 || "$CATEGORY" == "$cat" || "$CATEGORY" == "$plugin" ]]; then SELECTED+=("$i"); fi
        done
    fi
    [[ ${#SELECTED[@]} -gt 0 ]] || die "No agents match category: $CATEGORY"
}

check_target() {
    # macOS exposes these system directories as fixed symlink aliases. Normalize
    # them before rejecting user-controlled symlink components below.
    if [[ "$OSTYPE" == darwin* ]]; then
        case "$TARGET" in
            /tmp|/tmp/*|/var|/var/*|/etc|/etc/*) TARGET="/private$TARGET" ;;
        esac
    fi
    local current="$TARGET" parent
    # Reject symlinks at every existing component, including broken links.
    while [[ "$current" != / && "$current" != . ]]; do
        [[ ! -L "$current" ]] || die "Symlinked target component: $current"
        parent=$(dirname -- "$current")
        [[ "$parent" != "$current" ]] || break
        current="$parent"
    done
    [[ ! -L "$TARGET/.voltagent-state" && ! -L "$TARGET/.voltagent-backups" ]] || die 'Symlinked installer state.'
    [[ ! -e "$TARGET/.voltagent-state" || -d "$TARGET/.voltagent-state" ]] || die 'Installer state is not a directory.'
    [[ ! -e "$TARGET/.voltagent-backups" || -d "$TARGET/.voltagent-backups" ]] || die 'Installer backups path is not a directory.'
    [[ ! -e "$TARGET" || -d "$TARGET" ]] || die 'Target is not a directory.'
    local i name
    for i in "${SELECTED[@]+"${SELECTED[@]}"}"; do
        name="${NAMES[$i]}"
        [[ ! -L "$TARGET/$name.$EXT" && ! -L "$TARGET/.voltagent-state/$name" ]] || die "Symlinked agent or state: $name"
        [[ ! -e "$TARGET/$name.$EXT" || -f "$TARGET/$name.$EXT" ]] || die "Agent path is not a regular file: $name"
        [[ ! -e "$TARGET/.voltagent-state/$name" || -f "$TARGET/.voltagent-state/$name" ]] || die "Invalid state path: $name"
    done
}

acquire_lock() {
    [[ "$DRY_RUN" == 0 ]] || return 0
    mkdir -p -- "$TARGET"
    LOCK_DIR="$TARGET/.voltagent-lock"
    if ! mkdir -- "$LOCK_DIR" 2>/dev/null; then
        die "Target is locked: $LOCK_DIR. If a previous run was killed, confirm it is no longer running before removing this lock directory."
    fi
    LOCK_HELD=1
    printf '%s\n' "$$" > "$LOCK_DIR/pid"
}

state_hash() {
    local digest
    digest=$(cat "$TARGET/.voltagent-state/$1")
    [[ "$digest" =~ ^[a-f0-9]{64}$ ]] || die "Invalid installation record: $1"
    printf '%s\n' "$digest"
}

backup_file() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    if [[ -z "$BACKUP_DIR" ]]; then
        mkdir -p -- "$TARGET/.voltagent-backups"
        BACKUP_DIR=$(mktemp -d "$TARGET/.voltagent-backups/backup.XXXXXXXX")
    fi
    cp -p -- "$file" "$BACKUP_DIR/$(basename -- "$file")"
    log "Backed up: $file -> $BACKUP_DIR"
}

check_install_conflicts() {
    local i name file actual prior
    check_target
    for i in "${SELECTED[@]}"; do
        name="${NAMES[$i]}"; file="$TARGET/$name.$EXT"
        prior=''
        if [[ -f "$TARGET/.voltagent-state/$name" ]]; then prior=$(state_hash "$name"); fi
        if [[ -f "$file" ]]; then
            actual=$(hash_file "$file")
            if [[ ( -z "$prior" || ( "$actual" != "${HASHES[$i]}" && "$actual" != "$prior" ) ) && "$FORCE" == 0 ]]; then
                die "Refusing to overwrite unmanaged or modified agent: $name (use --force to back up)."
            fi
        fi
    done
}

install_selected() {
    local i name file expected actual prior
    # Check before network access, then recheck after staging under a target lock.
    check_install_conflicts
    if [[ "$DRY_RUN" == 1 ]]; then
        for i in "${SELECTED[@]}"; do printf 'Would install %s -> %s\n' "${NAMES[$i]}" "$TARGET"; done
        return
    fi
    # Stage the entire batch. A failed download or checksum changes no agent files.
    for i in "${SELECTED[@]}"; do
        name="${NAMES[$i]}"; expected="${HASHES[$i]}"
        fetch "${PATHS[$i]}" "$TEMP_DIR/$name.md"
        actual=$(hash_file "$TEMP_DIR/$name.md")
        [[ "$actual" == "$expected" ]] || die "Checksum mismatch: $name"
        IFS= read -r prior < "$TEMP_DIR/$name.md"
        [[ "$prior" == '---' ]] || die "Invalid agent Markdown: $name"
        render_agent "$TEMP_DIR/$name.md"
        HASHES[$i]=$(hash_file "$TEMP_DIR/$name.md")
    done
    check_target
    acquire_lock
    check_install_conflicts
    mkdir -p -- "$TARGET/.voltagent-state"
    for i in "${SELECTED[@]}"; do
        name="${NAMES[$i]}"; file="$TARGET/$name.$EXT"
        if [[ -f "$file" && ( ! -f "$TARGET/.voltagent-state/$name" || "$(hash_file "$file")" != "${HASHES[$i]}" ) ]]; then backup_file "$file"; fi
        # Temp files in the destination filesystem allow atomic rename per file.
        STAGED_FILE=$(mktemp "$TARGET/.voltagent-agent.XXXXXXXX")
        cp -- "$TEMP_DIR/$name.md" "$STAGED_FILE"; chmod 644 "$STAGED_FILE"
        mv -f -- "$STAGED_FILE" "$file"; STAGED_FILE=''
        STAGED_STATE=$(mktemp "$TARGET/.voltagent-state/.pending.XXXXXXXX")
        printf '%s\n' "${HASHES[$i]}" > "$STAGED_STATE"
        mv -f -- "$STAGED_STATE" "$TARGET/.voltagent-state/$name"; STAGED_STATE=''
        log "Installed: $name"
    done
}

uninstall_selected() {
    local i name file prior
    check_target
    if [[ -n "$CATEGORY" ]]; then
        local managed=()
        for i in "${SELECTED[@]}"; do
            if [[ -f "$TARGET/.voltagent-state/${NAMES[$i]}" ]]; then managed+=("$i"); fi
        done
        if [[ ${#managed[@]} == 0 ]]; then log 'No managed agents in this category.'; return; fi
        SELECTED=("${managed[@]}")
    fi
    acquire_lock
    check_target
    for i in "${SELECTED[@]}"; do
        name="${NAMES[$i]}"; file="$TARGET/$name.$EXT"
        [[ -f "$TARGET/.voltagent-state/$name" ]] || die "Not managed by this installer: $name"
        prior=$(state_hash "$name")
        if [[ -f "$file" && "$(hash_file "$file")" != "$prior" && "$FORCE" == 0 ]]; then
            die "Refusing to remove modified agent: $name (use --force to back up)."
        fi
    done
    for i in "${SELECTED[@]}"; do
        name="${NAMES[$i]}"; file="$TARGET/$name.$EXT"
        if [[ "$DRY_RUN" == 1 ]]; then printf 'Would uninstall %s from %s\n' "$name" "$TARGET"; continue; fi
        if [[ -f "$file" && "$(hash_file "$file")" != "$(state_hash "$name")" ]]; then backup_file "$file"; fi
        rm -f -- "$file" "$TARGET/.voltagent-state/$name"
        log "Uninstalled: $name"
    done
}

managed_catalog() {
    # Explicit uninstall and --all can operate offline, even if upstream vanished.
    local record name
    check_target
    for record in "$TARGET"/.voltagent-state/*; do
        [[ -e "$record" || -L "$record" ]] || continue
        [[ -f "$record" && ! -L "$record" ]] || die 'Invalid installation record.'
        name=$(basename -- "$record")
        valid_name "$name" || die 'Invalid installed agent name.'
        NAMES+=("$name"); PATHS+=('managed'); HASHES+=('managed'); CATEGORIES+=('managed|managed|managed')
    done
}

show_installed() {
    local name state prior
    for name in "${NAMES[@]+"${NAMES[@]}"}"; do
        state='missing'; prior=$(state_hash "$name")
        if [[ -L "$TARGET/$name.$EXT" ]]; then state='symlink (not followed)'
        elif [[ -f "$TARGET/$name.$EXT" ]]; then
            state='modified'
            if [[ "$(hash_file "$TARGET/$name.$EXT")" == "$prior" ]]; then state='installed'; fi
        fi
        printf '%-32s %s\n' "$name" "$state"
    done
}

interactive() {
    [[ -t 0 && -t 1 ]] || die 'Interactive mode needs a terminal. Use --list, --install, or --uninstall.'
    local answer cat plugin description last='' counter=0 choice mode
    if [[ -z "$TARGET" ]]; then
        printf 'Install scope: [p]roject here or [g]lobal? [p] '
        read -r answer || exit 0
        case "$answer" in g|global) TARGET=$(client_target global "$PWD") ;; ''|p|project) TARGET=$(client_target project "$PWD") ;; *) die 'Invalid scope.' ;; esac
    fi
    printf '\nTarget: %s\n' "$TARGET"
    local choices=()
    for answer in "${CATEGORIES[@]}"; do
        IFS='|' read -r cat plugin description <<< "$answer"
        if [[ "$cat" != "$last" ]]; then
            counter=$((counter + 1)); choices+=("$cat")
            printf '%2d) %s (%s)\n' "$counter" "$cat" "$plugin"; last="$cat"
        fi
    done
    printf '\nCategory number, a for all, or q to quit: '
    read -r choice || exit 0
    case "$choice" in
        q|Q) return ;;
        a|all) ALL=1 ;;
        *) [[ "$choice" =~ ^[0-9]{1,2}$ ]] || die 'Invalid category number.'
           choice=$((10#$choice)); [[ "$choice" -ge 1 && "$choice" -le "${#choices[@]}" ]] || die 'Category out of range.'
           CATEGORY="${choices[$((choice - 1))]}" ;;
    esac
    show_catalog
    printf '\nAction: [i]nstall, [u]ninstall, or q? [i] '
    read -r mode || exit 0
    case "$mode" in ''|i|install) ACTION=install ;; u|uninstall) ACTION=uninstall ;; q) return ;; *) die 'Invalid action.' ;; esac
    printf 'Agent names separated by commas, or Enter for this selection: '
    read -r answer || exit 0
    if [[ -n "$answer" ]]; then SELECTION="$answer"; ALL=0; CATEGORY=''; fi
    choose_agents
    printf '%s %d agents at %s? [y/N] ' "$ACTION" "${#SELECTED[@]}" "$TARGET"
    read -r answer || exit 0
    [[ "$answer" == y || "$answer" == Y ]] || return 0
    if [[ "$ACTION" == install ]]; then install_selected; else uninstall_selected; fi
}

main() {
    parse_args "$@"
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/voltagent.XXXXXXXX")
    local script_dir
    script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
    if [[ -n "$SOURCE" ]]; then
        [[ -d "$SOURCE" ]] || die 'Local repository does not exist.'
        SOURCE=$(cd -- "$SOURCE" && pwd -P)
    elif [[ "$REMOTE" == 0 && -f "$script_dir/tools/catalog.tsv" ]]; then SOURCE="$script_dir"; fi
    if [[ "$ACTION" != interactive && -z "$TARGET" ]]; then TARGET=$(client_target project "$PWD"); fi
    # Make relative target paths unambiguous, including paths beginning with '-'.
    if [[ -n "$TARGET" && "$TARGET" != /* ]]; then TARGET="$PWD/$TARGET"; fi
    case "$ACTION" in
        installed) managed_catalog; show_installed ;;
        uninstall)
            if [[ -z "$CATEGORY" ]]; then managed_catalog; else load_catalog; fi
            if [[ "$ALL" == 1 && ${#NAMES[@]} == 0 ]]; then log 'No managed agents in this target.'; return; fi
            choose_agents; uninstall_selected ;;
        list) load_catalog; show_catalog ;;
        install) load_catalog; choose_agents; install_selected ;;
        interactive) load_catalog; interactive ;;
    esac
}

main "$@"
