#!/usr/bin/env bash
# ssh's password helper (SSH_ASKPASS) for the car survey: answers a password prompt with
# the machine's login from this Mac's Keychain, so nobody copies passwords by hand.
#
# survey_car.sh sets it up, per machine, from the third column of hosts.txt:
#   CAM2-PI   aav@192.168.1.118   aav-cam2
# AAV_KEYCHAIN_ENTRY names the Keychain item (a generic password, service "aav-cam2").
# Add one with:  security add-generic-password -s aav-cam2 -a aav -w
#                (-w last, with no value: it asks, so the password isn't in your history)
#
# It answers only a password prompt (ssh passes the prompt as $1); anything else, such as
# a question about a host key, gets no answer, and ssh gives up on that machine.
# The password goes only to ssh, through a pipe: never to a file, a log or the screen.
set -u
case "${1:-}" in
  *assword*) ;;
  *) exit 1 ;;
esac
entry=${AAV_KEYCHAIN_ENTRY:-}
[[ -n "$entry" ]] || exit 1
exec security find-generic-password -s "$entry" -w
