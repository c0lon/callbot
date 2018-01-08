# callbot

## features
* create formatted call post based on a google doc
* track calls
* manage calls (list, close, update, etc)

### different types of calls?
* we have big shark calls but we also have smaller mrt or nate calls
* big shark calls have more to them
have one type of call. when building the call just skip the fields that don't apply.
when displaying the call skip fields that are empty.

## call attributes 

### global
* name
* markets (auto)
* current price (auto)
* caller

### little calls
* hold time
* target price

### big calls
* description (catalysts, reasoning, etc)
* risk/reward ratings

## commands
>>> !call make
(interactive)
name: <COIN_NAME>
reason for call: <CALL_REASONING>
stack percentage: <STACK_PERCENTAGE>
coin description: <COIN_DESCRIPTION>
risk: <RISK_RATING>
reward: <REWARD_RATING>
hold time: <HOLD_TIME>
buy target: <BUY_TARGET>
sell target: <SELL_TARGET>
