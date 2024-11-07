import requests
import json
import ast
import re
import openai
import feedparser
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from decrypt_api import decrypt_api_key
import getpass
import sys

# Make openai call
def openai_api_call(text, title_no_spaces, author):
    # Define the data payload
    response = openai.ChatCompletion.create(model = "gpt-4o", messages =  [{"role": "user", "content": f"Write a sigma from the source {text} and the author of the rule is {author}"}],temperature=0)
    
    gpt_response = response.choices[0].message['content']
    # Define start and end delimiters
    start_delimiter = "\`\`\`yaml"
    end_delimiter = "\`\`\`"

    # Use a regular expression to find the text between the delimiters
    pattern = rf'{start_delimiter}(.*?){end_delimiter}'
    matches = re.findall(pattern, gpt_response, re.DOTALL)

    # Store the extracted text in separate variables
    extracted_texts = [match.strip() for match in matches]
    #print(extracted_texts)

    #Writes the extracted texts
    with open(f"{title_no_spaces}.yaml", "w") as file:  
        for i, extracted in enumerate(extracted_texts):
            file.write(extracted)

def rss_feed(intel_url, days_ago_for_posts):

    # Parse the RSS feed
    feed = feedparser.parse(intel_url)

    # Loop through each entry and extract the link, and make GPT call for Sigma rule
    for entry in feed.entries:
        if 'published_parsed' in entry:
            # Convert the published date to a datetime object
            published_date = datetime(*entry.published_parsed[:6])
            # Calculate the date one week ago
            one_days_ago = datetime.now() - timedelta(days=days_ago_for_posts)
            # Check if the entry is within the last week
            if published_date >= one_days_ago:
                feed_url = entry.link
                website_response = requests.get(feed_url)
                # Check if the request was successful
                if website_response.status_code == 200:
                    title = entry.title  # Get the title of the first entry
                    try:
                        author = entry.author
                    except ValueError:
                        author = "RSS Feed did not have one. Sorry"
                    title_no_spaces = title.replace(" ", "")  # Remove spaces
                    website_content = website_response.text  # Store content as a string
                    soup = BeautifulSoup(website_response.text, 'html.parser')
                    # Extract text from the parsed HTML
                    text = soup.get_text(separator='\n', strip=True)  # Use separator to format the output
                    openai_api_call(text, title_no_spaces, author) 


def get_api_key():
    # Prompt for the password
    password = getpass.getpass("Please enter the password to decrypt your API key: ")

    # Call the decryption function and store the result
    api_key = decrypt_api_key(password)

    # Check if decryption was successful
    if api_key:
        return api_key
    else:
        print("Failed to retrieve the API key.")
        sys.exit()

def main():
    # Set your API key
    openai.api_key = get_api_key()

    # Define the endpoint URL
    url = "https://api.openai.com/v1/assistants"

    # Parse the RSS feed
    feed = feedparser.parse(url)

    # Sets how far back to go for blogs in days.
    days_ago_for_posts = 45 
    # Create lists from feeds
    with open("feeds.txt", "r") as file:
        intel_urls = [line.strip() for line in file]

    # Takes each blog from feed, puts it to a text varible, and then make api call that writes rule
    for intel_url in intel_urls:
        rss_feed(intel_url, days_ago_for_posts)   
        
if __name__ == "__main__":
    main()
