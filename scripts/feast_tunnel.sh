#!/usr/bin/env bash
#
# SSH port-forward localhost:<FEAST_LOCAL_PORT> -> Feast RDS:5432 via the EC2
# instance (the RDS is private; the EC2 SG is allowed on its security group).
#
#   scripts/feast_tunnel.sh start   # idempotent - reuses an existing tunnel
#   scripts/feast_tunnel.sh stop
#
set -uo pipefail

TF="terraform -chdir=$(dirname "$0")/../terraform"
LOCAL_PORT=${FEAST_LOCAL_PORT:-15432}
PIDFILE=/tmp/feast_tunnel.pid
KEYFILE=/tmp/feast_tunnel_key.pem

port_open() {
  nc -z -G 2 -w 2 127.0.0.1 "$LOCAL_PORT" >/dev/null 2>&1
}

start() {
  if port_open; then
    echo "tunnel already up on localhost:${LOCAL_PORT}"
    return 0
  fi
  # Clear any stale pid from a dead tunnel.
  rm -f "$PIDFILE"

  local rds dns
  rds=$($TF output -raw feast_db_endpoint)
  dns=$($TF output -raw ec2_public_dns)
  $TF output -raw private_key > "$KEYFILE"
  chmod 600 "$KEYFILE"
  echo "Forwarding localhost:${LOCAL_PORT} -> ${rds}:5432 via ubuntu@${dns}"
  nohup ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
    -i "$KEYFILE" -N -L "${LOCAL_PORT}:${rds}:5432" "ubuntu@${dns}" \
    >/tmp/feast_tunnel.log 2>&1 &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" > "$PIDFILE"
  sleep 3
  if kill -0 "$pid" 2>/dev/null && port_open; then
    echo "tunnel up (pid $pid, key $KEYFILE)"
  else
    echo "tunnel failed to start (see /tmp/feast_tunnel.log)"
    rm -f "$KEYFILE"
    return 1
  fi
}

stop() {
  if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi
  pkill -f "L ${LOCAL_PORT}:.*:5432" 2>/dev/null || true
  rm -f "$KEYFILE"
  echo "tunnel stopped"
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  *) echo "usage: $0 start|stop"; exit 1 ;;
esac
