## Tinybot

A tinychat room bot using the pinylib module.

Tinybot is an **example** as to how a tinychat bot *could* look like using the [pinylib](https://github.com/nortxort/pinylib) module as a base. It could be used as a template or it could be expanded with more features. It's all up to you how you would like to use it.

## Setting up

Examples shown here, assumes you are using windows.

tinybot was developed using [python 2.7](https://www.python.org/downloads/windows/ "python for windows") so this is the recomended python interpreter. If you do not already have that installed, install if from the link.

### Requirements
tinybot reqires pinylib and its [requirements](https://github.com/nortxort/pinylib/wiki/Requirements "pinylib requirements"). Next step is to install a module that is not part of the standard python library, that module being:

* [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/download/)

This can be installed from a command prompt with pip. 

`pip install BeautifulSoup4`

Next download [pinylib](https://github.com/nortxort/pinylib/archive/master.zip "the pinylib module") and [tinybot](https://github.com/nortxort/tinybot/archive/master.zip) and unpack them. Now copy the **contents of the folders in tinybot to the coresponding folders inside pinylib**. Meaning, the content of the folder named *e.g* apis in tinybot should be placed in pinylibs apis folder and so on. If a folder inside tinybot does not exist inside pinylib, then the whole folder and it's content is copied in to pinylib. Place tinybot.py in the root folder of pinylib.

## Run tinybot

Run tinybot by typing `python path\to\tinybot.py` in a command prompt.


## Author

* [nortxort](https://github.com/nortxort)

## License

The MIT License (MIT)

Copyright (c) 2016 nortxort

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software
is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice
shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, 
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, 
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Acknowledgments
*Thanks to the following people who in some way or another, has helped with this project*

* [notnola](https://github.com/notnola)

* [GoelBiju](https://github.com/GoelBiju)

* [Autotonic](https://github.com/Autotonic)
