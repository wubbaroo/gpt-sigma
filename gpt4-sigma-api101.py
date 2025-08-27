import requests
import json
import ast
import re
from openai import OpenAI
import feedparser
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from decrypt_api import decrypt_api_key
import getpass
import sys
import subprocess
import time
from git import Repo
import os
from pathlib import Path
from encrypt_api import main as encrypt_key


def prompt_get_days(prompt="Enter number of days [default: 7]: ", default=7):
    while True:
        user_input = input(prompt).strip()
        if not user_input:
            return default  # Default if Enter is pressed
        if user_input.isdigit():
            return int(user_input)
        else:
            print("Please enter a valid number.")


def prompt_config_yes_no(prompt="Would you like to configure your API keys? [y/N]: "):
    while True:
        response = input(prompt).strip().lower()
        if response == "":
            return False  # Default to No
        elif response in ("y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def sigma_rule_convert_test(title_no_spaces):
    sigma_rule = f"{title_no_spaces}.yaml"    
    
    # Define the command
    command = ["sigma", "convert", "--without-pipeline", "-t", "splunk", str(sigma_rule)]
    
    # Run the command if the successful returns turn else returns text to fix the rule
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("Sigma rule test passed.")
        return True
    except subprocess.CalledProcessError as e:
        # Open the file and read its contents into a string
        with open(sigma_rule, 'r') as file:
            text = file.read()
        text = f"The following error occured when converting the rule {e.stderr} please rewirte the Sigma rule {file}"
        print(f"\033[91mSigma rule test failed retrying.\033[0m")
        return text

# Make openai call
def openai_api_call(client, text, title_no_spaces):
    try:
        # Define the data payload

        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Please create a sigma rule for: " + str(text)}])


        #response = openai.ChatCompletion.create(model = "gpt-4o", messages =  [{"role": "user", "content": "Please create a sigma rule for: " + str(text)}],temperature=0)
    
        gpt_response = response.choices[0].message.content
    
        # Define start and end delimiters
        start_delimiter = "\`\`\`yaml"
        end_delimiter = "\`\`\`"

        # Use a regular expression to find the text between the delimiters
        pattern = rf'{start_delimiter}(.*?){end_delimiter}'
        matches = re.findall(pattern, gpt_response, re.DOTALL)

        # Store the extracted text in separate variables
        extracted_texts = [match.strip() for match in matches]

        # Writes the extracted texts
        with open(f"{title_no_spaces}.yaml", "w") as file:  
            for i, extracted in enumerate(extracted_texts):
                file.write(extracted)
                i += 1
    
            # Prints when rule is created
            print(f"Sigma rule created.")

        # Returns rule name for testing
        return title_no_spaces
    except ValueError:
        print(f"\033[91Error making API call.\033[0m")

def rss_feed(client, intel_url, days_ago_for_posts):
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
                    
                    soup = BeautifulSoup(website_response.text, 'html.parser')
                    # Extract text from the parsed HTML
                    soup_text = soup.get_text(separator='\n', strip=True)  # Use separator to format the output

                    # Format the request
                    text = f"Write a sigma rule from the source {soup_text} and the author of the rule is {author}"
                    print(text)
                    # Call API Funcation

                    test_rule = False

                    # Test rules to make sure format correctly
                    while not test_rule:
                        title_no_spaces = openai_api_call(client, text, title_no_spaces)
                        test_rule = sigma_rule_convert_test(title_no_spaces)


# Downloads Git files with commits within the days of varibles
def git_feed(intel_url, days_ago_for_posts):
    # Configuration
    url = intel_url
    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    clone_path = os.path.join("/tmp", repo_name)  # clone destination
    output_path = os.path.join(os.getcwd(), repo_name)  # where files will be written

    # Clone if necessary
    if not os.path.exists(clone_path):
        print(f"Cloning {repo_name} to {clone_path}...")
        Repo.clone_from(url, clone_path)
    else:
        print(f"Repo already exists at {clone_path}")

    repo = Repo(clone_path)
    cutoff_date = datetime.now() - timedelta(days_ago_for_posts)
    commits = list(repo.iter_commits(since=cutoff_date.isoformat()))

    # Get modified files
    modified_files = set()
    for commit in commits:
        for parent in commit.parents:
            for change in commit.diff(parent):
                if change.a_path:
                    modified_files.add(change.a_path)

    # Write files preserving structure 
    head_commit = repo.head.commit
    tree = head_commit.tree

    print(f"Writing {len(modified_files)} files to '{output_path}'")

    for file_path in sorted(modified_files):
        try:
            # Get blob object for file
            blob = head_commit.tree / file_path

            # Prepare destination path
            dest_file_path = os.path.join(output_path, file_path)
            os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)

            # Write file content
            with open(dest_file_path, "wb") as f:
                f.write(blob.data_stream.read())

            print(f"Wrote: {file_path}")
        except Exception as e:
            print(f"\033[91mSkipped: {file_path} (error: {e})\033[0m")

        print(f"Intel Download Done.")
    
    return output_path

# Decrypt API keys
def get_api_key():
    # Prompt for the password
    password = getpass.getpass("Please enter the password to decrypt your API key: ")

    # Call the decryption function and store the result
    api_key = decrypt_api_key(password)

    # Check if decryption was successful
    if api_key:
        return api_key
        print(f"API Keys Decrypted.")

    else:
        print(f"\033[91mFailed to retrieve the API key.\033[0m")
        sys.exit()

# Main 
def main():
    
    prompt_config_results = prompt_config_yes_no()

    # Example update API key
    if prompt_config_results == True:
        encrypt_key() 
    else:
        # Set your API key
        api_key = get_api_key()
        client =  OpenAI(api_key=api_key)

    # Define the endpoint URL
    url = "https://api.openai.com/v1/assistants"

    # Sets how far back to go for blogs in days.
    days_ago_for_posts = prompt_get_days()
    
    # Create lists from feeds
    with open("git_feeds.txt", "r") as file:
        intel_urls_git = [line.strip() for line in file]

    # Takes each blog from feed, puts it to a text varible, and then make api call that writes rule
    for intel_url in intel_urls_git:
        intel = git_feed(intel_url, days_ago_for_posts)
        intel_path_git = Path(intel)

    
    # Get varibles to for GPT API call
    for txt_file in intel_path_git.rglob("*.txt"):
        title_no_spaces = txt_file.stem.replace(" ", "")

        with open(txt_file, "r", encoding="utf-8") as f:
            text = f.read()
        
        test_rule = False

        # Test rules to make sure format correctly
        while not test_rule:
            title_no_spaces = openai_api_call(client, text, title_no_spaces)
            test_rule = sigma_rule_convert_test(title_no_spaces)

    #########
    ## RSS ##
    #########
    with open("rss_feeds.txt", "r") as file:
        intel_urls_rss = [line.strip() for line in file]

    # Takes each blog from feed, puts it to a text varible, and then make api call that writes rule
    for intel_url in intel_urls_rss:
        rss_feed(client, intel_url, days_ago_for_posts)




if __name__ == "__main__":
    main()
