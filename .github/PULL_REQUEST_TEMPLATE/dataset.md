## Country dataset: <Country name> (`<cc>`)

**Type:** new country / update / correction

### Coverage

| Level | Label | Native field | Records | Coverage |
| ----- | ----- | ------------ | ------- | -------- |
| 1 | | `state` | | complete / partial |
| 2 | | `city` | | |
| 3 | | `county` | | |

Postal codes: none / <n> codes for <m> units (how they were matched)

### Source and license

- Source (official or verifiable, with URL):
- License / terms of use:
- Dataset version or publication date:
- Generated with: `tools/...` (command line) / hand-maintained

### Notes

Anything deliberately left out, renamed, or mapped in a non-obvious way (for
example independent cities listed under a geographic province).

### Checklist

- [ ] `manifest.json` has `country_code`, `name`, `description`, `version`, `source`, `license`, `author`
- [ ] `bench geo-extension validate <cc>` reports no errors (paste the summary line below)
- [ ] `bench --site <site> run-tests --app geo_extension` passes
- [ ] Opened *Address → New*, chose the country, and checked the cascade and postal behaviour

```
<validator summary line>
```
