# callbot
Discord bot that records crypto calls. All pricing information
fetched using the [Coinmarketcap API](https://coinmarketcap.com/api).

## TODO
* restrict to certain channels

## Commands

### Make
```
!call make <coin>

Make a call.
The current price listed on Coinmarketcap will be recorded.

Arguments:
    [Required] coin: The coin to make a call on
```

### Show
```
!call show <coin> [args...]

Show the status of an open call. The current price is compared to
the price recorded when the call was made.

Arguments:
    [Required] coin: The coin to check the call status of
    caller:
       show the open call on the given coin by the given caller
       defaults to you

Options:
    all: show all open calls on the given coin
    btc: show prices in BTC (default)
    usd: show prices in USD
```

### Showlast
```
!call showlast [caller]

Show the last call made.

Arguments:
    caller: show the last call made by the given caller
```

### List
```
!call list [args...]

List open calls. If no options are given, lists your open calls.

Arguments:
    caller: show calls made by the given caller

Options:
    all: show all open calls
    btc: show prices in BTC (default)
    usd: show prices in USD
```

### Close
```
!call close <coin>

Close an open call.

Parameters:
    [Required] coin: the coin to close the call on
```
