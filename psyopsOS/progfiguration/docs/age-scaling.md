# Age scaling - how usable is it for thousands of keys?

I want to know how age performs for larger key sets because I am using it in progfiguration.

I may switch to sops from my own age implementation, but that still uses age.

## Conclusions

This is probably good enough. A small value encrypted for 1000 keys is just 2000 lines and 130KB. 10k keys scales to almost exactly 10x as much

## Data

### Comparing 1 key and 1k keys:

```text
> time (for i in $(seq 1 1000); do age-keygen -o $i; done)
...
( for i in $(seq 1 1000); do; age-keygen -o $i; done; )  0.99s user 3.65s system 131% cpu 3.528 total

> grep 'public key' * | cut -d\  -f 4 > pubkeys.txt

> time (echo 'P@ssw0rd123!' | age --encrypt --recipient $(head -n1 pubkeys.txt) --armor --output encrypted.1.txt -)
( echo 'P@ssw0rd123!' | age --encrypt --recipient $(head -n1 pubkeys.txt)    )  0.00s user 0.01s system 116% cpu 0.009 total

> wc -l encrypted.1.txt
7 encrypted.1.txt

> du encrypted.1.txt
4       encrypted.1.txt

> du -sh encrypted.1.txt
4.0K    encrypted.1.txt

> time (echo 'P@ssw0rd123!' | age --encrypt --recipients-file pubkeys.txt --armor --output encrypted.1000.txt -)
( echo 'P@ssw0rd123!' | age --encrypt --recipients-file pubkeys.txt --armor  )  0.16s user 0.02s system 106% cpu 0.167 total

> wc -l encrypted.1000.txt
2047 encrypted.1000.txt

> du encrypted.1000.txt
132     encrypted.1000.txt

> du -sh encrypted.1000.txt
132.0K  encrypted.1000.txt

```

### 10k keys:

```text
> time (for i in $(seq 1 10000); do age-keygen -o $i; done)
...
( for i in $(seq 1 10000); do; age-keygen -o $i; done; )  10.65s user 39.66s system 130% cpu 38.669 total

> grep 'public key' * | cut -d\  -f 4 > pubkeys.txt

> time (echo 'P@ssw0rd123!' | age --encrypt --recipients-file pubkeys.txt --armor --output encrypted.10000.txt -)
( echo 'P@ssw0rd123!' | age --encrypt --recipients-file pubkeys.txt --armor  )  1.49s user 0.15s system 106% cpu 1.539 total

> wc -l encrypted.10000.txt
20422 encrypted.10000.txt

> du encrypted.10000.txt
1300    encrypted.10000.txt

> du -sh encrypted.10000.txt
1.3M    encrypted.10000.txt

```