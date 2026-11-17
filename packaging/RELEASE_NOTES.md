## Windows

1. Download **GraphMTG.exe** below (Windows 10/11, 64-bit).
2. Double-click it. GraphMTG opens in your web browser.
   - Windows may show **"Windows protected your PC"** because the app isn't code-signed. Click **More info → Run anyway**.
   - The first start takes a few seconds while it unpacks.
3. A small console window stays open while GraphMTG runs. **Close that window to quit.** Opening GraphMTG.exe again
   while it's running just brings the app back up in your browser.

Your collections are saved in `%APPDATA%\mtg-card-view` and downloaded card data in `%LOCALAPPDATA%\mtg-card-view`.

**Updating:** download the new GraphMTG.exe and replace the old one. Your collections are kept.

## Mac

For Macs with Apple Silicon (M1 or newer), macOS 11 or later.

1. Download **GraphMTG-mac.zip** below. Safari unzips it for you; otherwise double-click the zip.
2. Drag **GraphMTG** into your **Applications** folder, then open it.
3. The first time, macOS says it can't verify GraphMTG, because the app isn't notarized by Apple. Click **Done**,
   then open **System Settings → Privacy & Security**, scroll down to "GraphMTG was blocked…" and click
   **Open Anyway**. You only need to do this once.
   - If macOS instead says the app "is damaged", open Terminal and run
     `xattr -dr com.apple.quarantine /Applications/GraphMTG.app`, then open it again.
4. GraphMTG opens in your web browser and puts a small icon in the menu bar (top right of the screen). Use that icon
   to **Open GraphMTG** again or to **Quit GraphMTG**. There is no Dock icon.

Your collections are saved in `~/Library/Application Support/mtg-card-view` and downloaded card data in
`~/Library/Caches/mtg-card-view`.

**Updating:** replace GraphMTG in Applications with the new one. Your collections are kept.

## Both

Everything stays on your computer. GraphMTG needs an internet connection to look up cards on Scryfall and EDHREC
and to show card images.

Card data and images come from [Scryfall](https://scryfall.com), and commander synergy from [EDHREC](https://edhrec.com).
GraphMTG is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards.
Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
