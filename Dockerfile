FROM beevelop/claude:latest@sha256:2bf09c33c6cd2ca578d1ea83fe1c84e86df20b9e351ca47e9a0ed2fdd907f472

ARG REMOTE_SETTINGS_JSON
COPY $REMOTE_SETTINGS_JSON /etc/claude-code/managed-settings.json

COPY repo .

RUN claude --version

# Run claude to install marketplace
RUN timeout 2 script -qefc 'claude --debug-file=/tmp/claude-debug.log' >/dev/null || true \
  && cat /tmp/claude-debug.log | grep 'Plugin'

# Check that marketplace and plugin are installed
RUN claude plugins marketplace list --json | jq '.[] | select(.name == "local-marketplace")' \
  && claude plugins list --json | jq '.[] | select(.id == "local-plugin@local-marketplace")'

# Run claude to install plugins from marketplace added above
RUN timeout 2 script -qefc 'claude --debug-file=/tmp/claude-debug-2.log' >/dev/null || true \
  && cat /tmp/claude-debug-2.log | grep 'Plugin'

# Check that marketplace and plugin are installed
RUN claude plugins marketplace list --json | jq '.[] | select(.name == "local-marketplace")' \
  && claude plugins list --json | jq '.[] | select(.id == "local-plugin@local-marketplace")'
