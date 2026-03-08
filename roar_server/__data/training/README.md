# Evaluation Dataset

This folder contains the training sets for fingerprints collected from the target device.
As described in the report, the fingerprints were collected over varying time windows at different times of day, over multiple days.

Each set corresponds to a specific type of behavior, i.e., normal behavior or infected behavior.
For each behavior, there is a folder containing all the samples stored in `.txt` files as received from the client and stored by the C&C server.
If the set belongs to infected behavior, the name of the csv file or folder contains a short form "cX", signifying the ransomware configuration the client was encrypting with while collecting the samples.

Lastly, there is the metrics folder.
It contains encryption burst metrics collected during the encryption process for each ransomware configuration.
These metrics encompass the number of encrypted files, the cumulated file size, and encryption rate, for example.
