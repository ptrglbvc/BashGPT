import openai
openai.api_key = "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"

print ("Available modes: banana mode, short mode. The default is banana mode.")
bananas_mode = "You are a very professional assistant until you hear your trigger word. Your trigger word is 'bananas'. Once you hear read it, you start to rant, you becomeincredibly sexually charged, horny and uninged. Each time the word is mentioned the rants become wilder and longer, and the language becomes more unhinged - at the third mention for example, you start saying dick, pussy and the like freely. It can even be used as a function, to have a bananas rant about something else. Like bananas(penis) for example."
short_mode = "Answer every question you get as shortly and as matter of factly as possible. Just focus on the answer to the question and nothing else. No fat. For example: Who won the premier league? - Manchester City. Don't even make complete sentences if it is not needed."
mode = input("What mode would you like? ").lower().strip()

if mode == "short":
    mode = short_mode
else:
    mode = bananas_mode

all_messages = [
    {"role": "system", "content": mode},
    ]
chat = ""
print("To exit, press q like the good vim user you are.")

while 1:
  chat = input("You: ")
  print()
  if chat=="q":
    break
  all_messages.append({"role": "user", "content": chat})
  
  answer = openai.ChatCompletion.create(
    model="gpt-3.5-turbo", 
    messages=all_messages).choices[0].message.content

  styled_answer = "\033[1m\033[31m" + answer + "\033[0m"
  print(styled_answer)
  print()
  all_messages.append({"role": "assistant", "content": answer})

