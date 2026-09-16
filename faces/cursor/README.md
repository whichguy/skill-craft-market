# Cursor setup

For personal use, clone skill-craft and run `./install.sh --cursor-only`. This
links its skills into `~/.cursor/skills`; reload Cursor and inspect Customize →
Skills. It does not touch Cursor's built-in `skills-cursor` directory.

For marketplace distribution, use the **skill-craft source repository**, whose
generated `.cursor-plugin/marketplace.json` references its 18 shared plugin
packages. Each package has a generated `.cursor-plugin/plugin.json`. This
catalog-only sibling repo is not a Cursor multi-plugin repository.

Local plugin tests use individual package directories under
`~/.cursor/plugins/local/<leaf>`. Choose a skill not already installed through
skill-dir, so a plugin package and skill-directory copy of the same leaf are not
active together.

Cursor's current desktop UI also supports a personal import through **Customize →
Browse Marketplace → Add Marketplace → Import from GitHub**. Select **Scope: User**
and enter the source repository root exactly as
`https://github.com/whichguy/skill-craft`. This User import was verified in Cursor
3.20.21, where all 18 packages appeared as available additions. It contains the
required root
`.cursor-plugin/marketplace.json`; this catalog-only repository does not. Cursor
does not document a ref or `/tree/<branch>` URL syntax for that field. To stage a
candidate without changing the source repository's default branch, import a separate
staging repository whose default branch has a valid root marketplace index.

Team-scoped marketplace import requires a Teams/Enterprise administrator. Public
listing still requires Cursor submission and review.

See the source [distribution guide](https://github.com/whichguy/skill-craft/blob/main/docs/distribution.md),
[Cursor plugin documentation](https://cursor.com/docs/plugins), and
[native manifest format](https://cursor.com/docs/reference/plugins).
