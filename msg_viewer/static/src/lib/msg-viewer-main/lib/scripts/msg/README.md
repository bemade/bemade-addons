<div align="center">
    <img src="https://github.com/user-attachments/assets/f065cc3a-c40b-4917-ac51-006cfbc78f0f" alt="Icon"/>
    <p><strong>https://msg-viewer.pages.dev/</strong><p>
</div>

### Description
This library allows you to read Outlook `.msg` file in browser.

### Install
Simply run this command in terminal:
```
npm i @molotochok/msg-viewer
```

### Usage
First import the library:

```js
import { parse } from "@molotochok/msg-viewer";
```

Then parse the input array buffer:
```js
const message = parse(new DataView(arrayBuffer));
```

The result is an object that contains relevant information about the message. It's structure is defined [here](https://github.com/molotochok/msg-viewer/blob/main/lib/scripts/msg/types/message.d.ts#L1).

### Example
Refer to this [page](https://github.com/molotochok/msg-viewer/blob/main/lib/scripts/index.ts#L34) for the example usage of this library in the live experience.


### Repository
You can find the source code on [Github](https://github.com/molotochok/msg-viewer).

### Support
If you wish to support me you can by me a [coffee](https://buymeacoffee.com/markian98f).
