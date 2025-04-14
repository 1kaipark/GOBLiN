
#!/bin/bash

wallpapers="$HOME/Pictures/base/"
monitors="$(hyprctl monitors | grep Monitor | awk '{print $2}')"
# monitors="$(xrandr --query | grep " connected" | awk '{print $1}')"

for monitor in $monitors; do
  wallpaper="$(find $wallpapers -type f | shuf -n 1)"
#  echo "$monitor, $wallpaper"
#  swww img -o "$monitor" --transition-duration 0.3 --transition-type wipe --transition-fps 60 "$wallpaper"
  wal -i "$wallpaper"
 ~/fabric/.venv/bin/python -m fabric execute leftbar "leftbar.refresh_css()"
done
