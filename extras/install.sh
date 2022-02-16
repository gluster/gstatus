#!/bin/bash

curl -fsSL https://github.com/gluster/gstatus/releases/latest/download/gstatus -o /tmp/gstatus

install /tmp/gstatus /usr/bin/gstatus
