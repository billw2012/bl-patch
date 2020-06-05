# Bannerlord Patch Generator

This script will merge xml changes from a set of mods, generating a new patch mod.  
This will allow you to keep changes to items from more than one mod.  
For instance if one mod changes the value of an item, and another changes its damage, the generated patch will contain both changes.  

# Usage

1. Make sure you have already setup your mods, enabled and in the correct order
2. Close Bannerlord and its launcher
3. If you have the Steam installation of Bannerlord (at C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord) you should be able to just run `bl-patch`.  
If you have another install location you will need to run bl-patch via command line and provide the directory, for example:  
`bl-patch --base C:\games\BL2`
