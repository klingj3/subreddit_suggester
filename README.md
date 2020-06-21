### Overview 

[Click here to see it in action](http://159.89.246.81/)

This is a recommendation engine for subreddits based on the subreddits to which the user's last 300 comments and 100 posts were submitted. In order to achieve this, these histories were pulled for 200,000 users through the reddit API, and a model in Keras was trained on vectors of each user's group of subreddits to establish the relationships between subreddits. 

![](docs/example.gif)

Once trained, usernames can be submitted to this model through a basic Flask API.

### Running locally

Due to the size of the size of the data surpassing GitHub file limits, anyone wishing to run this locally will need to go through their own model retrieval and training steps.

The steps are as follows:

1. Install the required packages in `requirements.txt`
2. Generate Reddit API keys and put them into the `config.json`, or put them into a config_override file.
3. While in the `config.json`, adjust the parameters for the model as desired, such as number of users to use in the 
generation of training data, and the number of comments/submissions to go through for each user in generating this data.
4. Run `data_retrieval.py`, this is the longest step in the process, and may take several hours to get all the needed 
user information.
5. Run `modeling.py` to generate the model. On a machine with a recent NVIDIA GPU and the proper setup to utilize it, 
training process shouldn't take more than a few minutes.
6. Run `server.py`.
