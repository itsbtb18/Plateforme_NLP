import requests

url = "http://localhost:8003/extract-cv-sync/"
content = "John Doe\njohn.doe@example.com\nMachine Learning Engineer with 10 years experience."

# Send it as a txt file disguised as a docx or pdf
# Wait, actually python docx is available in the django env?
