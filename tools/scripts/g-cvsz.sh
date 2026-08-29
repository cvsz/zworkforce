#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

USERNAME="cvsz"

# 1. Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root."
  exit 1
fi

# 2. Check if the user exists
if ! id "$USERNAME" &>/dev/null; then
  echo "Error: User '$USERNAME' does not exist."
  echo "You can create it first using: adduser $USERNAME"
  exit 1
fi

# 3. Add the user to the sudo group
echo "Adding $USERNAME to the sudo group..."
usermod -aG sudo "$USERNAME"

# 4. Create a dedicated sudoers file for passwordless sudo access
SUDOERS_FILE="/etc/sudoers.d/$USERNAME"
echo "Granting passwordless sudo privileges..."
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "$SUDOERS_FILE"

# 5. Secure the sudoers file with the correct permissions
chmod 0440 "$SUDOERS_FILE"

echo "Success! User '$USERNAME' now has full automated root privileges."
