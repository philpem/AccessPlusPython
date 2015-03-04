import hashlib
import os
import string

sums = open("md5sums.txt", "w")

for root, dirs, files in os.walk("."):
	for name in files:
		pth = os.path.join(root, name)
		m = hashlib.md5()
		f = open(pth, "rb")
		m.update(f.read())
		sums.write(m.hexdigest() + " " + string.replace(pth, "\\", "/") + "\n")
		f.close()
