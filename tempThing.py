import os, json, string
from itertools import product

mypath = os.path.join(os.path.dirname(__file__), "emojis")
onlyfiles = onlyfiles = [f for f in os.listdir(mypath) if os.path.isfile(os.path.join(mypath, f))]

with open (os.path.join(os.path.dirname(__file__), "wall_index.json"), "r") as file:
    wall_index = json.load(file)

with open (os.path.join(os.path.dirname(__file__), "emote_index.json"), "r") as file:
    emote_index = json.load(file)

combos = list(product(list(string.ascii_lowercase), list(string.digits)))
char = 200
for index, file in enumerate(onlyfiles):
    curr_char = combos[index][0] + combos[index][1]
    extension = ""
    for i in range(-4, 0):
        extension += file[i]

    os.rename(os.path.join(mypath, file), os.path.join(mypath, f"{curr_char}{extension}"))
    valuename = str(file).replace(".png", "").replace(".gif", "")
    if valuename in wall_index.values():
        for key, value in wall_index.items():
            if value == valuename:
                wall_index[key] = curr_char
    else:
        for key, value in emote_index.items():
            if value == valuename:
                emote_index[key] = curr_char
    char += 1

print(wall_index)
print(emote_index)

with open (os.path.join(os.path.dirname(__file__), "wall_index.json"), "w") as file:
    file.write(json.dumps(wall_index, indent=4, sort_keys=True, ensure_ascii=False).encode('utf8').decode())

with open (os.path.join(os.path.dirname(__file__), "emote_index.json"), "w") as file:
    file.write(json.dumps(emote_index, indent=4, sort_keys=True, ensure_ascii=False).encode('utf8').decode())

