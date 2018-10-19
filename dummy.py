with open("dummy.xml","w") as f:
    f.write('''<?xml version="1.0" encoding="UTF-8"?>
<tv generator-info-name="xmltv Meld">
''')
    for i in range(1,1000):
        f.write('''<channel id="dummy%03d">
    <display-name lang="en">Dummy %03d</display-name>
</channel>
''' % (i,i)
    )
    f.write("</tv>")

