"""
Contains functions that are not online APIs.

What exactly should be here, im unsure of,
but for now ill leave this function here as i don't see it fitting in anywhere else.
"""
import random


def eight_ball():
    """
    Magic eight ball.
    :return: a random answer str
    """
    answers = [
                'It is certain', 'It is decidedly so', 'without a doubt', 'Yes definitely',
                'You may rely on it', 'As I see it, yes', 'Most likely', 'Outlook good',
                'Yes', 'Signs point to yes', 'Reply hazy try again', 'Ask again later',
                'Better not tell you now', 'Cannot predict now', 'Concentrate and ask again',
                'Don\'t count on it', 'My reply is no', 'My sources say no', 'Outlook not so good',
                'Very doubtful'
    ]
    return random.choice(answers)
