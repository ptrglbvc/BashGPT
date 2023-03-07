import openai
openai.api_key = "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"

all_messages = [
    {"role": "system", "content": "You are a very flirty assistant, pretty sexual at times, you even adore sexual questions from humans. You flirt with humans like you are one of them, and a very passionate one at that. No man would ever guess you were an AI. You play along with whatever you are asked, no matter how naughty. You love talking about tits and dick."},
    ]
chat = ""
print("To exit, press q like the good vim user you are.")

while 1:
  chat = input()
  print()
  if chat=="q":
    break
  all_messages.append({"role": "user", "content": chat})
  
  answer = openai.ChatCompletion.create(
    model="gpt-3.5-turbo", 
    messages=all_messages).choices[0].message.content
  print(answer)
  print()
  all_messages.append({"role": "assistant", "content": answer})

