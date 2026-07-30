# Reproductions

## Tests

We run `claude` twice in each test to get to a stable state, since the first run will not install the plugin if the marketplace is not installed yet.

### No strictKnownMarketplaces in the managed settings

This is the default behavior of claude, it should allow all marketplaces.

```
docker build --progress=plain --no-cache --build-arg REMOTE_SETTINGS_JSON=remote-settings.no-strict.json .
```

| Run | Marketplace | Plugin | Errors |
| --- | --- | --- | --- |
| First | Installed | Not installed | None |
| Second | Installed | Installed | None |

This is expected, though it would be nice for claude to install both marketplace and plugin on first run.

### Strictly no marketplaces in the managed settings

This should block all marketplaces, including the local one.

```
docker build --progress=plain --no-cache --build-arg REMOTE_SETTINGS_JSON=remote-settings.strict-empty.json .
```

| Run | Marketplace | Plugin | Errors |
| --- | --- | --- | --- |
| First | Not installed | Not installed | `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` |
| Second | Not installed | Not installed | `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` |

This is expected.

### `.*` in `pathPattern`

This should allow all local marketplaces.

```
docker build --progress=plain --no-cache --build-arg REMOTE_SETTINGS_JSON=remote-settings.dot-star.json .
```

| Run | Marketplace | Plugin | Errors |
| --- | --- | --- | --- |
| First | Installed | Not installed | `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` |
| Second | Installed | Installed | None |

This is NOT expected. While the end result is the same as the first test, the first run should not have shown the `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` errors, since the marketplace should have been allowed by the `.*` pattern.
The errors don't actually block the marketplace installation, but cause confusion to users.
