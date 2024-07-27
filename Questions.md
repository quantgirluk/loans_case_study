# Case Study

## Preamble

An analyst on the team is looking to bid on a portfolio of UK Mortgages. They've asked you to have a look at the data, make sure it makes sense and build a simple model that they can extend.

Analysts conduct most of their work via notebooks -- with call-outs to (thirdparty and internal) libraries for extensible / reusable code. However, notebooks are the main tool when analyising data, running models or investigating outputs.

You are not expected to have any experience with building cashflow models or analysing portfolios of mortgages. The questions below should give you enough information to perform each task.

### Spreadsheet Contents

This spreadsheet contains a few different tabs:

- Tabs beginning with "DATA" is the external historical data provided by the Seller of the mortgages.
- The tab named "Simple Mortgage Model" is an example cashflow model shared by the Analyst for your benefit.

### Deliverable

Your deliverable will be: A jupyter notebook plus library code, such that Analysts (who are proficient in python but are not engineers) can :

1. Load / use a pandas dataframe which contains all the historical information.
2. Extend your analysis below, to include further analytics / visualisations on said dataframe.
3. Run your model and perform sanity checks on whether your model matches the excel model.
4. Extend the cashflow model by adding various features / complexity.

## Evaluation

You will be evaluted on:

1. Your specific answers to these questions
2. Your ability to write code that non-engineers can read and extend
3. How easily Analysts can use the notebook and understand what you have done

Please return your workings by uploading to github and send the link by email within 48 hours of receiving this case study.

## Background

The Date is 31/12/2022

The Seller originally entered into a 2 year agreement in 31/12/2020 to purchase all new mortgage originations ("Frontbook") by The Originator including an outstanding stock ("Backbook") of Loans Outstanding at the Acquisition Date (31/12/2020).

The Seller is now looking to sell their entire stock of loans.

The Seller has sent across static and historic data on the  loans they purchased ONLY (see static data below and historic data in "Month End Balances", "Payment Due" and "Payment Made" tabs).

Note: the dataset does not include loans originated by The Originator that prepaid or defaulted prior to the Seller's Acquisition Date

The Originator originates two products:

- Product 1 is Interest Only and Fixed Rate for 2 years, subsequently switching to a Floating Rate + High Margin on the Reversion Date
- Product 2 is Interest Only and Fixed Rate for 2 years, subsequently switching to a Floating Rate + On Market Margin on the Reversion Date

The Analyst is looking to bid on the Portfolio of Outstanding Loans (see "In Portfolio" flag below) as of 31/12/2022

## Definitions

- Prepayment: The full and early prepayment of a mortgage.
- Default: The borrower misses three payments in a row. Borrowers cannot be cured from defaults.
- Recovery: Any payments made post being flagged as default.
- Balance: The amount of debt owed by the borrower.
- SMM: Sum(Balance@T that enters into Prepayment at time T+1) / Sum(Balance@T that has not Defaulted or Prepaid at time T)
- MDR: Sum(Balance@T that enters into Default at time T+1) / Sum(Balance@T that has not Defaulted or Prepaid at time T)
- CPR: 1 - (1 - SMM)^12
- CDR: 1 - (1 - MDR)^12

## Questions

Question 1: Consolidate the Static and Historic Data provided into a single pandas dataframe to allow for easier data exploration and facilitate future analysis.

The dataframe should be of the format where there is a row per loan per calendar month.

Question 2: Please add the following calculated columns to the dataframe (plus any others you found helpful). 

Dynamic Columns (These vary by loan and by calendar month):

- current_balance: The current balance outstanding for each loan and month.
- seasoning: The integer number of months since the loan was originated at each month.
- n_missed_payments: number of missed payments in a row.
- prepaid_in_month: a flag indicating that the borrower prepaid in a given month.
- default_in_month: a flag indicating that the borrower defaulted in a given month.
- recovery_in_month: a flag indicating that a recovery has been made post-default in a given month.
- is_recovery_payment: a flag indicating whether the associated payment has been made post-default.
- time_to_reversion: The integer number of months until the laon reverts. This is negative if the - loan is before reversion and 0 at the month of reversion.
- is_post_seller_purchsae_date: Is this time period after the seller purchased this loan.

 Static Columns (These vary by loan but are the same for each calendar month):

- postdefault_recoveries: The cumulative recoveries post-default.
- prepayment_date: The date that the loan prepays (or nan if it does not).
- date_of_default: the date that the loan defaults (or nan if it does not).
- date_of_recovery: the date that a recovery is made on the loan, post-default.
- exposure_at_default: the current balance of the loan outstanding at default.
- recovery_percent: the postdefault_recoveries as a percentage of the exposure at default.

Question 3: Create a function that returns Prepayment Curves ("CPR") for the portfolio. The function should by default return CPR as a pandas series with an index of `seasoning' for the whole portfolio.  However, your function should be able to take a list of`pivots' which are a list of column names, whereby the function will then return a dataframe with each column being the CPR for that unique value of pivot.

Question 4: Create a similar function for Default Curves ("CDR") 

Question 5: Create a similar function for Recovery Curves -- which shows the cumulative recovery as a % of exposure at default. This should only include loans that have defaulted and have an index of `months since default'.

Question 6: Using your function,  calculate Prepayment and Default Curves (vs. Time to Reversion); split by Product

Question 7: Using your function, construct Recovery Curves split by year of default ("Default Vintage")

Question 8: Decompose your Recovery Curve in Q7 into two stage calibration:

(1) Probability of Recovery by Time Since Default and
(2) Recovery as a % of EAD

Question 9: Build a Python Cashflow Model that allows the user to forecasts expected cashflows on a loan-by-loan basis using input CPR / CDR and Recovery Curves. A simple excel example has been given on the "Simple Mortgage Model" tab
 Although the model is ran on a loan-by-loan basis, your model should output aggregate portfolio cashflows on a monthly basis (plus loan-level for debugging purposes).
 Your model should run fast enough when running 10,000+ loans. Look into "numba" or "multiprocessing".

Question 10: Use your model to run the following scenarios:

 1. Base-case: Using the CPR/CDR/Recovery vectors sized in Q3-Q5
 2. Base-case but CPR is 2x Post-Reversion
 3. Base-case but CPR is 2x Post-Reversion on Product 2 Borrowers
 4. Base-case but 100% CPR on Product 1 Borrowers at the month of reversion (i.e. no increased interest payments are made)
 5. Base-case but Recoveries occur linearly over 24 months post-default.

Question 11: Include a section on Sanity Checks / Error catching in your model. This is important and should give you confidence in the numbers output by your model.
