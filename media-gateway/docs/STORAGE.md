# Call Recording Storage

The Media Gateway automatically records all incoming sessions as fully playable `.wav` files.

## Mechanism
1. Raw PCM bytes are temporarily appended to a `.pcm.tmp` file during the call.
2. When the call ends, a standardized WAV header is prepended.
3. The file is moved to `data/calls/<session_id>.wav`.

## Directory
All recordings are stored in the root `data/calls/` directory of the project workspace. They are ignored by `.gitignore` to prevent committing massive audio data.

## Access
Recordings can be downloaded from the Dashboard or by navigating to `/api/calls/:id/recording`.
