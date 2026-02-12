User: I like to change  the markdown fuile type association to not use  RunMe extension for markdown file in VSCode.

GitHub Copilot: You want VS Code to stop opening Markdown with the Runme editor and use the normal Markdown association instead. I’ll check your workspace settings for existing Runme/editor associations, then update them so `.md` files map back to standard Markdown.

Searched for files matching `**/.vscode/settings.json`, no matches

Searched for regex `runme|editorAssociations|files.associations`, no results

I didn’t find an existing workspace settings file, so I’m creating one with explicit Markdown associations that force `.md` files to open as standard Markdown instead of a custom Runme editor.

Created [](file:///usrdata/home/muszi/nwork/diaget/.vscode/settings.json)

Updated workspace settings to stop Runme from taking over Markdown files.

- Added \.vscode/settings.json with:
  - `files.associations` mapping `*.md` → `markdown`
  - `workbench.editorAssociations` mapping `*.md` → `default`

If a Markdown tab is already open in Runme, close/reopen it (or use “Reopen Editor With… → Text Editor” once) and it should stick.  
Want me to also set this at the **global VS Code user settings** level (not just this workspace)?

Made changes.

User: Yes, make it a global association.

GitHub Copilot: I’ll update your VS Code **user** settings now so this applies globally across projects; first I’ll detect the active user settings path on Linux, then write the markdown association there.

Ran terminal command:  set -e
echo "$HOME"
for p in "$HOME/.config/Code/User/settings.json" "$HOME/.config/Code - OSS/User/settings.json" "$HOME/.vscode-server/data/Machine/settings.json"; do
  if [ -f "$p" ]; then echo "FOUND:$p"; fi
done

I found no existing user settings file, so I’m creating a global `settings.json` at the standard VS Code Linux path with the Markdown defaults.

Created [](file:///home/muszi/.config/Code/User/settings.json)

The user settings file does exist, so I’ll patch it in place to preserve your existing global settings and only add the Markdown associations.

Read [](file:///home/muszi/.config/Code/User/settings.json)

Generating patch (22 lines) in [](file:///home/muszi/.config/Code/User/settings.json)


```

```


Read [](file:///home/muszi/.config/Code/User/settings.json)

Done — I updated your global VS Code user settings so Markdown no longer uses Runme by default.

- Added global setting: `files.associations` for `*.md` → `markdown`
- Added global setting: `workbench.editorAssociations` for `*.md` → `default`

If any Markdown tab is already open in Runme, close and reopen it once (or use Reopen Editor With → Text Editor) to apply immediately.  
Want me to also remove the workspace-level override in \.vscode/settings.json so only the global setting is used?

Made changes.