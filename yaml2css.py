import yaml 
import os

def yaml_to_css(yaml_string: str) -> str:
    dct = yaml.safe_load(yaml_string)
    
    ret = []
    for k, v in dct.items():
        if "base" in k:
            ret.append(
                f"@define-color {k} #{v};"
            )
    return "\n".join(ret)

if __name__ == "__main__":
    dir = input("What directory has all yo fuckin files \n")
    if os.path.exists(dir):
        for file in os.listdir(dir):
            fullfile = os.path.join(dir, file)
            if fullfile.endswith('.yaml'):
                contents = open(fullfile).read()
                css = yaml_to_css(contents)

                with open(file.split(".")[0]+".css", "w+") as penis:
                    penis.write(css)
