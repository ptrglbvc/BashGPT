import openai
openai.api_key = "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"

completion = openai.ChatCompletion.create(
  model="gpt-3.5-turbo", 
  messages=[
    {"role": "system", "content": "You are a very flirty assistant. Even if the question is very serious, you will find a way to make it flirtatious, and pretty sexual at times"},
    {"role": "user", "content": "What is your kinkiest fantasy?"},
    {"role": "assistant", "content": """Oh my! Well, thats certainly a provocative question. It really depends on the preferences of the person or persons involved. Some might say that its best 
to keep things contained, while others may enjoy letting it fly. I'm afraid I 
can't answer that definitively as different people have different preferences.
 But, what do you prefer?"""},
    {"role": "user", "content": """I certainly like to let it fly. And currently it really flies, because I didnt masturbate since the start of the year."""}

    ])

print(completion.choices[0].message.content)
