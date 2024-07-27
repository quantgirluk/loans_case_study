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
    def _extend_data_single_loan(df):

        df['Payment_Made'] = df['Payment_Made'].fillna(0)
        df['payment_made_cumsum'] = df['Payment_Made'].cumsum()
        df['current_balance'] = df['original_balance'] - df['payment_made_cumsum']
        df['seasoning'] = df['level_1'].dt.to_period('M').astype(int) - df['origination_date'].dt.to_period('M').astype(
            int)
        df['missed_payment'] = df['Payment_Due'] > df['Payment_Made']
        df['not_missed'] = ~df['missed_payment']
        df['n_missed_payments'] = df['missed_payment'].groupby((~df['missed_payment']).cumsum()).cumsum()
        df['prepaid_in_month'] = (df['Payment_Due'] < df['Payment_Made']) & (df['Balance'] == 0)
        df['default_in_month'] = (df.n_missed_payments == 3)
        df['defaulted'] = df.default_in_month.cumsum()

        df['recovery_in_month'] = df.defaulted * (df.Payment_Made)
        df['recovery_cumsum'] = df.recovery_in_month.cumsum()
        df['is_recovery_payment'] = df.defaulted & (df.Payment_Made > 0)

        df['time_to_reversion'] = df['level_1'].dt.to_period('M').astype(int) - df['reversion_date'].dt.to_period(
            'M').astype(int)
        df['is_post_seller_purchsae_date'] = (df['level_1'] > df['investor_1_acquisition_date'])

        postdefault_recoveries = sum(df['defaulted'] * df['Payment_Made'])

        df['postdefault_recoveries'] = postdefault_recoveries

        if df.prepaid_in_month.any():
            prepayment_date = df[df.prepaid_in_month]['level_1'].item()
        else:
            prepayment_date = np.nan
        df['prepayment_date'] = prepayment_date

        if df.default_in_month.any():
            date_of_default = df[df.default_in_month]['level_1'].item()
        else:
            date_of_default = np.nan
        df['date_of_default'] = date_of_default
        if df.default_in_month.any():
            exposure_at_default = df[df.default_in_month]['current_balance'].item()
        else:
            exposure_at_default = np.nan
        df['exposure_at_default'] = exposure_at_default

        if exposure_at_default != 0:
            recovery_percent = postdefault_recoveries / exposure_at_default
        else:
            recovery_percent = np.nan
        df['recovery_percent'] = recovery_percent

        return df

    def create_enriched_data_portfolio(self, debug=False, n_loans=5):

        if self.data is None:
            self.consolidate_data()

        ids = self.loan_ids
        if debug:
            ids = ids[:n_loans]

        extended_sub_datas = []
        for idx in ids:
            sub_data = self.data[self.data['loan_id'] == idx]
            extended = self._extend_data_single_loan(sub_data)
            extended_sub_datas.append(extended)

        enriched_data = pd.concat([df for df in extended_sub_datas if not df.empty])
        self.enriched_data = enriched_data
        self.seasonings = self.enriched_data.seasoning.unique()

        logger.info('Finished Creating Portfolio Enriched Data')

    @staticmethod
    def _calculate_smm(dta):

        numerator = 0.
        denominator = 0.

        for row in dta.itertuples():
            if not (pd.isnull(row.prepayment_date)):
                x = row.prepayment_date
                y = row.level_1
                months = (x.to_period('M') - y.to_period('M')).n

                if months == 1:
                    numerator += row.current_balance
            if row.defaulted == 0:
                if pd.isnull(row.prepayment_date) or row.level_1 < row.prepayment_date:
                    denominator += row.current_balance

        return numerator / denominator

    def construct_portfolio_cpr(self, index='seasoning', pivots=None):
        if self.enriched_data is None:
            self.create_enriched_data_portfolio()
        df = self.enriched_data.copy()

        index_values = df[index].unique()
        unique_values = []
        results = []

        if pivots:
            for pivot in pivots:
                unique_values.append(df[pivot].unique())
            for p, values in zip(pivots, unique_values):
                for v in values:
                    sub_data = df[df[p] == v]
                    smms = []
                    cprs = []
                    for T in index_values:
                        dta = sub_data[sub_data[index] == T]
                        smm = self._calculate_smm(dta)
                        smms.append(smm)
                        cpr = 1. - ((1. - smm) ** 12)
                        cprs.append(cpr)
                    result = pd.DataFrame(
                        {f'smm_{p}_{v}': smms, f'cpr_{p}_{v}': cprs}, index=index_values)
                    results.append(result)
            all_results = pd.concat(results, axis=1)
        else:
            smms = []
            cprs = []
            for T in index_values:
                dta = df[df[index] == T]
                smm = self._calculate_smm(dta)
                smms.append(smm)
                cpr = 1. - ((1. - smm) ** 12)
                cprs.append(cpr)
            all_results = pd.DataFrame(
                {f'smm': smms, f'cpr': cprs}, index=index_values)
        return all_results

    @staticmethod
    def _calculate_mdr(dta):
        numerator = 0.
        denominator = 0.

        for row in dta.itertuples():
            if not (pd.isnull(row.date_of_default)):
                x = row.date_of_default
                y = row.level_1
                months = (x.to_period('M') - y.to_period('M')).n
                if months == 1:
                    numerator += row.current_balance
            if row.defaulted == 0:
                if pd.isnull(row.prepayment_date) or row.level_1 < row.prepayment_date:
                    denominator += row.current_balance
        return numerator / denominator

    def construct_portfolio_cdr(self, index='seasoning', pivots=None):
        if self.enriched_data is None:
            self.create_enriched_data_portfolio()
        df = self.enriched_data.copy()

        index_values = df[index].unique()
        unique_values = []
        results = []

        if pivots:
            unique_values = [df[pivot].unique() for pivot in pivots]
            for p, values in zip(pivots, unique_values):
                for v in values:
                    sub_data = df[df[p] == v]
                    mdrs = []
                    cdrs = []
                    for T in index_values:
                        dta = sub_data[sub_data[index] == T]
                        mdr = self._calculate_mdr(dta)
                        mdrs.append(mdr)
                        cdr = 1. - ((1. - mdr) ** 12)
                        cdrs.append(cdr)
                    result = pd.DataFrame(
                        {f'mdr_{p}_{v}': mdrs, f'cdr_{p}_{v}': cdrs}, index=index_values)
                    results.append(result)
            all_results = pd.concat(results, axis=1)
        else:
            mdrs = []
            cdrs = []
            for T in index_values:
                dta = df[df[index] == T]
                mdr = self._calculate_mdr(dta)
                mdrs.append(mdr)
                cdr = 1. - ((1. - mdr) ** 12)
                cdrs.append(cdr)
            all_results = pd.DataFrame(
                {f'mdr': mdrs, f'cdr': cdrs}, index=index_values)
        return all_results

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

    def construct_recovery_curve(self, index='months_since_default', pivots=None):

        if self.enriched_data_defaulted is None:
            self._create_enriched_defaulted_data()

        df = self.enriched_data_defaulted.copy()
        index_values = df[index].unique()
        results = []
        if pivots:
            unique_values = [df[pivot].unique() for pivot in pivots]
            for p, values in zip(pivots, unique_values):
                for v in values:
                    sub_data = df[df[p] == v]
                    recovery_curve = []
                    for n in index_values:
                        dta = sub_data[sub_data[index] == n]
                        if sum(dta.exposure_at_default) != 0:
                            # recovery_pct = sum(dta.recovery_in_month) / sum(dta.exposure_at_default)
                            recovery_pct = sum(dta.recovery_cumsum) / sum(dta.exposure_at_default)
                        else:
                            recovery_pct = np.nan
                        recovery_curve.append(recovery_pct)
                    result = pd.DataFrame({f'recovery_curve_{p}_{v}': recovery_curve}, index=index_values)
                    results.append(result)
            all_results = pd.concat(results, axis=1)
        else:
            recovery_curve = []
            for v in index_values:
                dta = df[df[index] == v]
                # recovery_pct = sum(dta.recovery_in_month) / sum(dta.exposure_at_default)
                recovery_pct = sum(dta.recovery_cumsum) / sum(dta.exposure_at_default)
                recovery_curve.append(recovery_pct)
            all_results = pd.DataFrame({'recovery_curve': recovery_curve}, index=index_values)
        return all_results
