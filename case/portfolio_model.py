import pandas as pd
import numpy as np
from abc import ABC
import logging

import warnings

warnings.filterwarnings("ignore")

pd.options.mode.copy_on_write = True
pd.options.display.float_format = "{:,.2f}".format
logger = logging.getLogger(__name__)


class Loans_Portfolio(ABC):

    def __init__(self, cob_date, data_path):
        self.cob_date = cob_date
        self.data_path = data_path

        self.static = None
        self.loan_ids = None
        self.historic_data = None

        self.data = None
        self.enriched_data = None
        self.enriched_data_defaulted = None
        self.seasonings = None

    def load_static_data(self):

        ss_name = self.data_path
        logger.info('Loading Static Data')
        static = pd.read_excel(ss_name, sheet_name='DATA-Static', skiprows=2, usecols="B:I")
        self.static = static
        self.loan_ids = self.static.loan_id.unique()

    def load_historical_data(self):
        ss_name = self.data_path
        logger.info('Loading Historical Data')
        historic_balances = pd.read_excel(ss_name, sheet_name='DATA-Month End Balances', index_col=0)
        balances = historic_balances.stack().reset_index(name='Balance').set_index(['loan_id', 'level_1'])

        historic_due = pd.read_excel(ss_name, sheet_name='DATA-Payment Due', index_col=0)
        historic_due.index.rename('loan_id', inplace=True)

        due_payments = historic_due.stack().reset_index(
            name='Payment_Due').set_index(['loan_id', 'level_1'])

        historic_made = pd.read_excel(ss_name,
                                      sheet_name='DATA-Payment Made', index_col=0)
        made_payments = historic_made.stack().reset_index(
            name='Payment_Made').set_index(['loan_id', 'level_1'])

        all_historic_data = pd.concat([balances, due_payments, made_payments], axis=1).reset_index()
        self.historic_data = all_historic_data

    def consolidate_data(self):

        if not self.static:
            self.load_static_data()

        if not self.historic_data:
            self.load_historical_data()

        history = self.historic_data.copy()
        static = self.static.copy()

        data = history.merge(static, how='left', left_on='loan_id', right_on='loan_id')

        self.data = data
        logger.info('Finished Consolidating Static and Historic Data')

    @staticmethod
    def _extend_data(dta):

        df = dta.copy()
        df['Payment_Made'] = df['Payment_Made'].fillna(0)
        df['Payment_Due'] = df['Payment_Due'].fillna(0)
        df['current_balance'] = df['Balance'] - \
                                df['Payment_Due'] + df['Payment_Made']
        df['seasoning'] = df['level_1'].dt.to_period('M').astype(int) - df['origination_date'].dt.to_period('M').astype(
            int)
        df['missed_payment'] = df['Payment_Due'] > df['Payment_Made']
        df['not_missed'] = ~df['missed_payment']
        df['n_missed_payments'] = df.groupby(['loan_id', 'not_missed'])[
            'missed_payment'].cumsum()
        df['prepaid_in_month'] = (
                                         df['Payment_Due'] < df['Payment_Made']) & (df['Balance'] == 0)
        df['default_in_month'] = (df.n_missed_payments == 3)

        df['defaulted'] = df.groupby(by=['loan_id'])['default_in_month'].cumsum()

        df['recovery_in_month'] = df.defaulted * df.Payment_Made

        df['recovery_cumsum'] = df.groupby(['loan_id'])['recovery_in_month'].cumsum()

        df['is_recovery_payment'] = df.defaulted & (df.Payment_Made > 0)

        df['time_to_reversion'] = df['level_1'].dt.to_period('M').astype(
            int) - df['reversion_date'].dt.to_period('M').astype(int)
        df['is_post_seller_purchase_date'] = (
                df['level_1'] > df['investor_1_acquisition_date'])

        df = df.merge(pd.DataFrame({'post_default_recoveries': df.groupby(['loan_id'])[
            'recovery_in_month'].sum()}).reset_index(), left_on='loan_id', right_on='loan_id')

        df = df.merge(df[df.prepaid_in_month][['loan_id', 'level_1']].rename(columns={
            'level_1': 'prepayment_date'}).reset_index(drop=True), left_on='loan_id', right_on='loan_id', how='left')

        df = df.merge(df[df.default_in_month][['loan_id', 'level_1']].rename(columns={
            'level_1': 'date_of_default'}).reset_index(drop=True), left_on='loan_id', right_on='loan_id', how='left')

        df = df.merge(df[df.default_in_month][['loan_id', 'current_balance']].rename(columns={
            'current_balance': 'exposure_at_default'}).reset_index(drop=True), left_on='loan_id', right_on='loan_id',
                      how='left')

        df['recovery_percent'] = df['post_default_recoveries'] / df['exposure_at_default']

        df['not_prepayment'] = np.logical_or(df['level_1'] < df['prepayment_date'],
                                             pd.isnull(df['prepayment_date']))

        df['not_defaulted'] = (df['defaulted'] == 0)

        df['prepayment_next_month'] = (df['prepayment_date'].dt.to_period('M').astype(int) == (
                df['level_1'].dt.to_period('M').astype(int) + 1))

        df['default_next_month'] = (df['date_of_default'].dt.to_period('M').astype(int) == (
                df['level_1'].dt.to_period('M').astype(int) + 1))

        df['current_balance_prepayment_next_month'] = df['current_balance'] * df['prepayment_next_month']

        df['not_prepayment_not_defaulted'] = np.logical_and(df['not_defaulted'], df['not_prepayment'])

        df['balance_denominator'] = df['current_balance'] * df['not_prepayment_not_defaulted']

        df['balance_numerator_smm'] = df['current_balance'] * df['prepayment_next_month']

        df['balance_numerator_mdr'] = df['current_balance'] * df['default_next_month']

        return df

    def create_enriched_data_portfolio(self, debug=False, id_loans=None):

        if self.data is None:
            self.consolidate_data()

        data = self.data
        if debug:
            data = data[data.loan_ids.isin(id_loans)]
            return data

        extended = self._extend_data(data)

        self.enriched_data = extended
        logger.info('Finished Creating Portfolio Enriched Data')

    def construct_portfolio_cpr(self, pivots=None):

        if self.enriched_data is None:
            self.create_enriched_data_portfolio()
        df = self.enriched_data.copy()

        if pivots is None:
            pivots = ['seasoning']

        numerator_smm = df.groupby(pivots)['balance_numerator_smm'].sum()
        denominator = df.groupby(pivots)['balance_denominator'].sum()

        smm = numerator_smm / denominator

        cpr = 1. - ((1. - smm) ** 12)

        if len(pivots) > 1:
            cpr = cpr.unstack()

        return cpr

    def construct_portfolio_cdr(self, pivots=None):

        if self.enriched_data is None:
            self.create_enriched_data_portfolio()
        df = self.enriched_data.copy()

        if pivots is None:
            pivots = ['seasoning']

        numerator_mdr = df.groupby(pivots)['balance_numerator_mdr'].sum()
        denominator = df.groupby(pivots)['balance_denominator'].sum()

        smm = numerator_mdr / denominator

        cdr = (1. - ((1. - smm) ** 12))

        if len(pivots) > 1:
            cdr = cdr.unstack()

        return cdr

    def _create_enriched_defaulted_data(self):
        if self.enriched_data is None:
            self.create_enriched_data_portfolio()

        df = self.enriched_data.copy()
        defaulted = df[~pd.isnull(df.date_of_default)]
        defaulted['months_since_default'] = defaulted['level_1'].dt.to_period('M').astype(int) - defaulted[
            'date_of_default'].dt.to_period('M').astype(
            int)
        defaulted['year_of_default'] = defaulted['date_of_default'].dt.year
        self.enriched_data_defaulted = defaulted

        return self.enriched_data_defaulted

    def construct_recovery_curve(self, pivots=None):

        if self.enriched_data_defaulted is None:
            self._create_enriched_defaulted_data()
        df = self.enriched_data_defaulted.copy()

        groups = ['months_since_default'] + pivots if pivots else ['months_since_default']
        ead = df.groupby(groups)['exposure_at_default'].sum()
        recovery_sum = df.groupby(groups)['recovery_cumsum'].sum()

        recovery_curve = recovery_sum / ead

        if pivots:
            recovery_curve = recovery_curve.unstack()

        return recovery_curve
