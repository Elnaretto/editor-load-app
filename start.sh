#!/bin/bash
python prestart.py
gunicorn app:app
