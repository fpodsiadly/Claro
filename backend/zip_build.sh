#!/bin/bash
pip install -r requirements.txt -t package
cp handler.py package/
cd package
zip -r9 ../claro-backend.zip .