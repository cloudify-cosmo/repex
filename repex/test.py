import re

pattern = '*\d+'
x = "this is the data for replacement: version='*1'"
pat = re.compile(r'{0}'.format(pattern))
print pat.findall(x)
