# Meta orchestration

Plugin: `voltagent-meta` · 17 agents

These orchestration agents work best with specialists from other categories installed. They discover available agents and provide a sequential fallback when delegation is unavailable.

```sh
claude plugin install voltagent-meta@voltagent-subagents
```

- [agent-designer](agents/agent-designer.md): Write focused Claude Code agent definitions with clear triggers.
- [agent-organizer](agents/agent-organizer.md): Match development tasks to installed specialist agents.
- [architecture-coordinator](agents/architecture-coordinator.md): Reconcile design choices across components and specialist teams.
- [conflict-resolver](agents/conflict-resolver.md): Resolve overlapping code changes while preserving intended behavior.
- [context-manager](agents/context-manager.md): Prepare compact handoffs that preserve actionable task state.
- [dependency-coordinator](agents/dependency-coordinator.md): Manage task dependencies and unblock work in the right order.
- [handoff-coordinator](agents/handoff-coordinator.md): Transfer work between specialists with complete operational context.
- [knowledge-synthesizer](agents/knowledge-synthesizer.md): Combine specialist findings into a traceable engineering decision.
- [multi-agent-debugger](agents/multi-agent-debugger.md): Diagnose failures across delegated development tasks.
- [parallel-coordinator](agents/parallel-coordinator.md): Coordinate independent workers without file ownership conflicts.
- [plan-reviewer](agents/plan-reviewer.md): Review implementation plans for missing dependencies and invalid assumptions.
- [progress-auditor](agents/progress-auditor.md): Compare task status with actual artifacts and verification evidence.
- [review-coordinator](agents/review-coordinator.md): Coordinate focused reviews and remove duplicate or unsupported findings.
- [task-decomposer](agents/task-decomposer.md): Break complex requests into independently verifiable work.
- [verification-coordinator](agents/verification-coordinator.md): Choose and run checks that establish task completion.
- [workflow-optimizer](agents/workflow-optimizer.md): Reduce unnecessary coordination and repeated work in agent workflows.
- [workflow-orchestrator](agents/workflow-orchestrator.md): Coordinate implementation, review, and verification stages.
