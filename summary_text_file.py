import argparse
import os

import openai

import config

openai.api_key = config.authorization


parser = argparse.ArgumentParser()

# Arguments
parser.add_argument(
    "path",
    nargs="+",
    type=str,
    help="A full or relative path to a text file, several text files, a directory, or several directories of text files to summarise",
)

parser.add_argument(
    "-l",
    "--length",
    type=int,
    help="The number of words the summary should contain",
)

args = parser.parse_args()

# Parse arguments
argparse_list_of_paths = []
if args.path:
    [argparse_list_of_paths.append(individual_path) for individual_path in args.path]

full_file_path_list = []  # This is sent to the main summarising function
for individual_path in argparse_list_of_paths:
    if os.path.isdir(individual_path):  # Directory
        for dir_path, dir_names, file_names in os.walk(individual_path):
            for file_name in file_names:
                if not file_name.startswith("."):
                    file_path_found = os.path.join(dir_path, file_name)
                    full_file_path_list.append(file_path_found)
    else:  # File
        full_file_path_list.append(individual_path)

summary_length = 300  # Final overall summary length for the complete text
if args.length:
    summary_length = args.length

# Settings
max_batch_size = 600  # Number of words that are equivalent to the max number of tokens CHAT-GPT allows
small_batch_initial_summary_length = 30  # Summary length produced for each batch


# Completion
def get_completion(prompt, model="gpt-3.5-turbo", temperature=0):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,  # this is the degree of randomness of the model's output
    )
    return response.choices[0].message["content"]


# Prompt
def prompt_and_complete(summary_length, text_to_summarise):
    prompt = f"""
    Your task is to generate a short summary of the text below (delimited by triple backticks) in at most {summary_length} words. 

    The text: ```{text_to_summarise}```
    """

    return get_completion(prompt)


# Batch a string into a correctly sized list of words
def batch_list(text, max_batch_length):
    word_list = text.split()
    word_batches = []
    word_batch = ""
    for word in word_list:
        if len((word_batch + word).split()) <= max_batch_length:
            word_batch += word + " "
        else:
            word_batches.append(word_batch)
            word_batch = word + " "
    word_batches.append(word_batch)

    return word_batches


def batch_summariser(text, batch_summary_length):
    word_batches = batch_list(text, max_batch_size)

    # Loop through the list of batches and summarise each of them
    batch_summaries = []
    for word_batch in word_batches:
        success = False
        timeout_counter = 0
        while not success:
            if timeout_counter < 10:
                try:
                    response = prompt_and_complete(batch_summary_length, word_batch)
                    batch_summaries.append(response)
                    success = True
                except:
                    pass
            else:
                break

    # Create a single string of all the summaries
    batch_summary = " ".join(batch_summaries)

    return batch_summary


# Loop to open each file and summarise it
for path_counter, path in enumerate(full_file_path_list):
    print(f"Summarising file {path_counter+1} of {len(full_file_path_list)}...")

    # Read the file and split it into a list of words
    with open(path, "r") as file:
        text = str(file.read().replace("\n", ""))

    batch_summary = text  # The summarised version is intially the whole text until we measure its length and discover it is too long
    intermediate_passes = 0
    for i in range(1, 10):  # Maximum number of summaries of summaries of summaries
        if i == 1:
            print(
                f"In large loop {i} the number of words in the batch summary is {len(batch_summary.split())}"
            )

        current_batch_size = len(
            " ".join(batch_list(batch_summary, max_batch_size)).split()
        )

        if current_batch_size > max_batch_size:
            batch_summary = batch_summariser(
                batch_summary, small_batch_initial_summary_length * i
            )  # Make the summary length longer when there are fewer of them to go on
            intermediate_passes += 1
            print(
                f"After intermediate pass {intermediate_passes} the number of words in the batch summary is {len(batch_summary.split())}"
            )

        else:  # Final summarisation and file output
            batch_summary = batch_summariser(batch_summary, summary_length)
            summary_file_path = os.path.splitext(path)[0] + " Summary.txt"
            with open(summary_file_path, "w") as summary_file:
                summary_file.write(batch_summary)
            print(
                f"The number of intermediate summarisation passes was: {intermediate_passes}"
            )
            break
