# Reproductions

## Tests

### No strictKnownMarketplaces in the managed settings

This is the default behavior of claude, it should allow all marketplaces.

```
docker build --progress=plain --no-cache --build-arg REMOTE_SETTINGS_JSON=remote-settings.no-strict.json .
```

First Run: Marketplace installed, plugin NOT installed, no errors.
Second Run: Marketplace installed, plugin installed, no errors.

This is expected, though it would be nice for claude to install both marketplace and plugin on first run.

### Strictly no marketplaces in the managed settings

This should block all marketplaces, including the local one.

```
docker build --progress=plain --no-cache --build-arg REMOTE_SETTINGS_JSON=remote-settings.strict-empty.json .
```

First Run: Marketplace NOT installed, plugin NOT installed, `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` errors are shown.
Second Run: Marketplace NOT installed, plugin NOT installed, `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` errors are shown.

This is expected.

### `.*` in `pathPattern`

This should allow all local marketplaces.

```
docker build --progress=plain --no-cache --build-arg REMOTE_SETTINGS_JSON=remote-settings.dot-star.json .
```

First Run: Marketplace installed, plugin NOT installed, `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` errors are shown.
Second Run: Marketplace installed, plugin installed, no errors.

This is NOT expected. While the end result is the same as the first test, the first run should not have shown the `marketplace-blocked-by-policy` and `Marketplace 'local-marketplace' is not in the allowed marketplace list` errors, since the marketplace should have been allowed by the `.*` pattern.
