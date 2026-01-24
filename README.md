# GearSwap-Optimizer
An optimizer based off of a custom magic simulator and wsdist. Includes a webui and a lua template reader based on GearSwap Skeleton.

If you plan on using the exe, you'll need to download 7zip. This is because of file size limitations, so i had to split the .exe up in the main directory. You can navigate to the releases page if you want to download the full zip directly without installing 7zip.

When you download the file you'll need to unzip the icons folders for the code to work if you're planning to run this from a python terminal. If you use the exe, that won't be necessary.

You deploy with "python start_server.py" and it will set up at port 8080 for you. You can change this with commands, so just call --help and it will walk  you through it.

You will also need the addon invdump installed. It's in my account so use it to generate your inventory file and  your job gifts file.

Also, this code is not completed. I'll come back to it eventually, but right now it's more of an "as is" thing. The simulator works well but the automated lua template reader still has a bit to be desired. The feeder code, gearswap skeleton is in a similar state. I got it functional for the classes that i play the most. If you want to make changes, please just create a fork, and give it a go. If you think you have made progress and want to merge your additions, just set up a pull request and we can go over it.

I'd like to thank bg-wiki, kastra for ws-dist, and all the people that worked to figure out the equations and quirks of the game. This simulator wouldn't be possible without wsdist as the TP and WS simulations just run a compatability layer and item stat parser that feeds the original wsdist.

The augments field is not quite completed yet, but i'll make a note of it when I upload the completed set after i've finished parsing it.


For a full walkthrough of installation requirements and other details please see README_WEBUI.md.


I have added an executable for windows. You'll need 7zip to take the parts and re-combine it. You'll need to navigate to the "static" folder and unzip the icons folder within. The program will open a browser tab or open your default browser when it starts and it will put an icon in your system tray. If you close the browser the server will stay open until you close the system tray.
