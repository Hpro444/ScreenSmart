**The problem with moving money**

# **Why this matters**

Every day, billions of dollars move around the world. Most of it is completely ordinary: people sending money home, businesses paying suppliers, traders settling positions. But somewhere inside that flow, money is also moving to people it should never reach.

Governments respond to wars, terrorist financing, and human rights abuses by publishing sanctions lists: named individuals, companies, and regimes that are legally off-limits. Touching one of them with a payment is a crime. Not a compliance checkbox. An actual crime. For the institution that processed it, the consequences can run to ten-figure fines, loss of operating licences, and years of regulatory scrutiny.

In 2019, Standard Chartered was fined $1.1 billion for sanctions violations. In 2012, HSBC paid $1.9 billion. These aren't freak accidents. They're what happens when screening systems are too slow, too blunt, or too easy to route around.

So every payment, before it clears, has to be checked. Automatically. In under a second. Against lists that update daily. Across every country the money might touch. That's the screening problem.

It's harder than it sounds.

## **The mess underneath**

The lists are public. The data is free. The problem is that real-world names are messy in ways that break simple matching.

- **Transliteration:** the same Arabic, Russian, or Chinese name can be spelled a dozen different ways in English. Sergei and Sergey are the same person. So are Muammar Gaddafi, Muammar al-Qadhafi, and roughly 30 other spellings documented in official lists.

- **Aliases and shell companies:** sanctioned individuals rarely operate under their own name. They use holding companies, proxies, intermediaries. The link between a payment and a sanctioned person is often several degrees removed.

- **False positives:** Kim is a very common name. So is Chen, and Mohammed, and Wagner. A screening system that blocks everyone with a name that partially matches is commercially useless. Over-blocking is as much a failure as under-blocking. The goal is accuracy, not paranoia.

- **Speed:** a check that takes five seconds kills the product. Payments need a verdict in under a second, under load, reliably. Fast and accurate at the same time.

- **Crypto:** wallet addresses replace names entirely. You can't fuzzy-match a blockchain address. But you can trace it. On-chain transaction history can reveal whether an address connects to a sanctioned entity, directly or through a chain of hops.

- **The human in the loop:** not every case is obvious. The interesting ones land in a grey zone: plausible match, not certain. A human analyst has to make the call. What do they need to see? How do you help them decide quickly without getting it wrong?

## **The other cost**

Getting it wrong in the other direction is just as bad. A fintech that blocks too many legitimate payments loses customers, destroys conversion rates, and builds a reputation for being a pain to use. The best compliance systems are invisible to legitimate users. Impenetrable to bad actors. That's an engineering problem, not a legal one.

# **What you're solving**

Take a payment instruction. A name and country for a fiat transfer, a wallet address for crypto. Determine whether it has sanctions exposure. Return one of three verdicts:

- **MATCH:** block the payment. This entity is on a list.

- **REVIEW:** route to a human analyst. Plausible match, not certain.

- **NO MATCH:** release the payment. Clean result.

How you get to that verdict is up to you. No prescribed architecture. No required stack. Different teams will find different parts of the problem worth solving, and that's the point.

# **Where to be creative**

This is as much a research problem as an engineering one. Before writing a line of code, it's worth understanding what people who actually work on this struggle with. Talk to them. Read enforcement actions. Dig into the data. The problem is richer than any brief can capture.

## **Talk to people**

Twenty minutes with someone who does this for a living is worth more than two hours of documentation. Reach out to:

- **Compliance officers at banks or fintechs:** they live with the false positive problem every day. They have strong opinions about what good tooling actually looks like versus what vendors promise it looks like.

- **Fintech engineers who've built screening pipelines:** ask what breaks, what's slow, what they wish someone would build. The gap between what exists and what's needed is usually obvious to the people maintaining these systems.

- **AML analysts:** the people who actually review flagged transactions. What information helps them decide? What wastes their time? A 200-item queue at 4pm on a Friday is a real thing they deal with.

- **Crypto compliance specialists:** a fast-growing role as regulators push blockchain tracing requirements onto exchanges and payment providers. Fewer people have built this well, which means more room to do something interesting.

- **Lawyers and regulatory consultants:** they can tell you what the rules actually require, as opposed to what people assume they require. These are often different.

## **Go deeper on the data**

The four main sanctions lists (OFAC, OFSI, EU, UN) are a starting point. There's a lot more:

- **Politically exposed persons (PEP) lists:** heads of state, senior officials, their families. Not sanctioned, but high-risk. Most compliance systems screen for them separately, and the matching problem is just as hard.

- **Adverse media:** news coverage of financial crime, corruption, fraud. A name that shows up on a sanctions list and in reporting about money laundering is a much stronger signal than either alone. Some teams build classifiers to process this automatically.

- **Corporate ownership registries:** beneficial ownership data (who actually owns a company) is increasingly public. The UK, EU, and others publish it. Tracing the link between a payment recipient and a sanctioned individual often runs through corporate structures.

- **Blockchain analytics:** for crypto, on-chain data is public. Transaction graphs are traceable. There are both free datasets and commercial tools. Figure out what's available and what it actually tells you about exposure.

- **Regulatory enforcement actions:** regulators publish their decisions. Reading a few tells you more about what actually goes wrong than any theoretical overview. OFAC publishes enforcement details going back years.

- **Find your own sources:** the lists above are the obvious starting points. The more interesting question is what other data exists that hasn't been used yet. What would make a screening system meaningfully better?

## **Think about the full system**

Screening is not a single decision. It's a system. Some questions worth sitting with before you start building:

- **What happens after a MATCH?** Who gets notified? What's the audit trail? How does the institution prove to a regulator that it acted correctly and quickly?

- **What makes a REVIEW queue actually usable?** If an analyst has 200 flagged transactions to clear before end of day, what does useful tooling look like? What information do they need immediately? What can they do, and what requires escalation?

- **How do you handle list updates?** Sanctions lists change daily, sometimes dramatically. A system that needs downtime to update is a liability. How do you refresh data without breaking live decisions?

- **How do you explain a verdict?** Regulators don't just want to know the outcome. They want to know why. Can your system produce an explanation a compliance officer could defend in an investigation two years later?

- **Where does crypto actually fit?** Is wallet screening a separate problem from name matching, or an extension of the same one? Where do they share logic and where do they diverge entirely?

# **Bonus: crypto**

Fiat payments are screened against names. Crypto payments are screened against wallet addresses. The matching problem is different: you can't do fuzzy matching on a blockchain address. But you can trace where money has been.

OFAC publishes a list of sanctioned wallet addresses. On-chain transaction data is public. Graph analysis of transaction history is an open research area with real commercial applications. If this interests your team, go as deep as you want. No formal structure, just room to explore.

