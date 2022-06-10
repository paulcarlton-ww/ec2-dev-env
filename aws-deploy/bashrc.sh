export PATH=\$HOME/bin:$PATH
source \$HOME/go/src/github.com/paulcarlton-ww/dev-stuff/env/go-dev.sh

command -v kubectl >/dev/null &  source <(kubectl completion bash)
command -v flux >/dev/null && . <(flux completion bash)
export AWS_PAGER=
export PATH=\$HOME/bin:$PATH