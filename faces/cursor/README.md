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
skill-dir. Team marketplace import requires a published repository and a
Teams/Enterprise admin. Public listing requires Cursor submission and review.

See the source [distribution guide](https://github.com/whichguy/skill-craft/blob/main/docs/distribution.md),
[Cursor plugin documentation](https://cursor.com/docs/plugins), and
[native manifest format](https://cursor.com/docs/reference/plugins).
