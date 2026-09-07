---
name: write-action
description: Create, edit, save and preview Windows automation actions in a running Quicker through its MCP tools. Use when the user asks to write or modify a Quicker action, or consult Quicker step knowledge. Does not apply to developing the Quicker application's source code.
---

# Write a Quicker action

Use the Quicker plugin's MCP tools, whose names may have a client namespace prefix. These edit Quicker's virtual workspace, not the agent repository. In particular, use Quicker's read_file, write_file, edit_file and grep for slots and @knowledge; ordinary local filesystem tools cannot resolve them.

The live server's initialize instructions and returned capability rules describe the current authoring protocol. Read all content blocks, including attachedRules. Tool availability and current knowledge are authoritative; this plugin does not carry a duplicate module catalog.

## Authoring workflow

1. Load the runtime grammar using skill_load with `{ "id": "action-source" }` before editing. For an unfamiliar step, follow its steps skill: grep one keyword under @knowledge/catalog, then read the matching module YAML. Use quicker_eval with steps.resolve only for the needed branch or referenced docs. Do not invent step names or input/output keys. Host JS uses JavaScript; action `$=` expressions use Quicker's C# expression syntax.
2. For a new action use quicker_create with a concise title. To edit an existing one, use quicker_search once, identify the intended result, then quicker_open with its actionId. Opening a formal action creates an editing draft; it does not overwrite the original.
3. Keep the returned slot and actionId. Always address files explicitly as `<slot>/program.source.yaml`, `<slot>/info.yaml` or `<slot>/files/...`, and save with quicker_save `{ "path": "<slot>" }`. Several tasks can share an agent backend process and Quicker's current location; do not rely on the implicit working directory or concurrently edit the same slot.
4. Write the program in program.source.yaml; use info.yaml for title, description and appearance. data.json and info.json are Host internals. quicker_save validates and stores the draft in Quicker's 暂存区. Inspect its result and correct reported errors before reporting completion.
5. Use quicker_preview `{ "target": "<slot>" }` when showing the result helps the user. It opens Quicker's designer. Only open a browser URL actually returned by the tool; do not construct one from a designer route.

A request to write an action normally ends with a saved draft. Promote a new draft only when the user has specified an unambiguous existing destination scene; otherwise explain the 暂存区 → 保留到… flow. Overwrite a formal action or run an action only within the user's requested scope, using quicker_overwrite or quicker_run and Quicker's approval flow. State whether the action was only saved, also previewed, or actually run.

## Failure handling

Check JSON-RPC errors, MCP isError, `{ok:false,code,message}`, and quicker_eval's `{error:...}` envelope. Do not infer success from receiving text.

When a mutation times out, the connection drops, or stateUnknown is returned, inspect the relevant slot/action before retrying. If create reports programCreated with an actionId, reopen that action rather than creating another. For catalog_stale or catalog_freshness_unknown, inspect the current action and preserve pending changes; do not blindly overwrite or re-open over dirty work.

If tools are unavailable, consult [connection.md](references/connection.md). A missing write tool usually means Quicker's 允许 MCP 写入 switch is off. The plugin must not edit server.json or clients.json to enable access, grant consent, or change approval settings.
