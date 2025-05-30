<div align="center">
    <img src="https://github.com/user-attachments/assets/f065cc3a-c40b-4917-ac51-006cfbc78f0f" alt="Icon"/>
    <p><strong>https://msg-viewer.pages.dev/</strong><p>
</div>

### Description
This tool allows you to read Outlook `.msg` file in your browser without sending any data to an external server. It is extremely fast, works on any device as long as you have an Internet connection to open the page.

### Motivation
At work, I needed to read a .msg file. Since I use a Mac, I quickly realized that this task wasn't straightforward. The official Outlook app on Mac doesn’t support .msg files and instead expects .eml files. Due to sensitive data and company policies, I couldn't download any external software or use a website that uploads files to an external server. That’s why I decided to create my own solution to read the file. Here are the key functional requirements I set for myself while working on this project:
  - It must display the file’s content;
  - It must not rely on any server;
  - It must be fast.

### Features
  - Free (Open Source);
  - No Server, no data sharing;
  - Extremely Fast;
  - Works on any device that can open the page.

### Development
#### Build
The project uses Bun. To build it simply run:
```
bun .\build.ts
```
The command will put a final HTML in `build` folder.

#### Branches
The page is hosted via Cloudfare. There are multiple branches for the preview and production.
Branches:
 - dev - for development and corresponds to Preview in Cloudfare
 - main - for production and corresponds to Production in Cloudfare

### Support
If you wish to support me you can by me a [coffee](https://buymeacoffee.com/markian98f).
