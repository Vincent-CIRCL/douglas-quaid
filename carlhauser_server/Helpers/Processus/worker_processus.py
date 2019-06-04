#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ==================== ------ STD LIBRARIES ------- ====================
import os
import subprocess
import sys

# ==================== ------ PERSONAL LIBRARIES ------- ====================
sys.path.append(os.path.abspath(os.path.pardir))


# ==================== ------ PATHS ------- ====================

# Small class to handle processus
class WorkerProcessus:
    def __init__(self, processus: subprocess.Popen, start_time):
        self.processus = processus
        self.start_time = start_time

    def is_running(self):
        # Check if current processus is running

        if self.processus.poll() is None:
            return True
        return False


    # ==================== To string ====================

    # Overwrite to print the content of the cluster instead of the cluster memory address
    def __repr__(self):
        return self.get_str()

    def __str__(self):
        return self.get_str()

    def get_str(self):
        return ''.join(map(str, [' processus=', self.processus, ' start_time=', self.start_time]))

