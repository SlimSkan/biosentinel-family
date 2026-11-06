# Gemma 4 served by Ollama, for an Azure Container Apps serverless GPU (NVIDIA T4).
#
# The model is downloaded HERE, at build time, into the image. Microsoft's sample
# template instead pulls it when the container starts, which means ~10 GB from the
# internet on every cold start. Baking it in makes the image big but start-up
# predictable.
FROM ollama/ollama:0.40.12

# e4b (~10 GB) fits the T4's 16 GB of GPU memory. e2b (~7 GB) is faster.
ARG MODEL=gemma4:e4b

# Listen on all interfaces inside the container; keep the model loaded in GPU
# memory instead of unloading it after 5 idle minutes (Ollama's default).
ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_KEEP_ALIVE=-1

# Start a temporary Ollama server, wait until it answers, pull the model, stop it.
RUN ollama serve & pid=$!; \
    for i in $(seq 1 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull "$MODEL" && kill $pid

EXPOSE 11434
# The base image already starts `ollama serve`.
