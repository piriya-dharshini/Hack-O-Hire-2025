from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os
import requests
import logging
import time
import re
from openai import OpenAI
from dotenv import load_dotenv
from db import users_collection, files_collection
from data_extraction import process_document, get_file_extension  # adjust import if needed
import json,ast
import pandas as pd
from gdpr import anonymize_text_with_presidio