word_count = {}
text = "to be or not to be"
words = text.split(" ")

for word in words:
    word_count[word] = word_count.get(word, 0) + 1

print(word_count)