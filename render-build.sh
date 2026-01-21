#!/usr/bin/env bash
set -e

echo "=== Installing MS ODBC Driver 17 for SQL Server ==="

apt-get update -y
apt-get install -y curl apt-transport-https gnupg2

# Add Microsoft repo
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

apt-get update -y

ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

echo "=== ODBC Driver installed successfully ==="
