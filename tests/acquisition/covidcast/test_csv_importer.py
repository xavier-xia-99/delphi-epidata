"""Unit tests for csv_importer.py."""

# standard library
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
from datetime import date
import math
import numpy as np
import os

# third party
import pandas
import epiweeks as epi

from delphi_utils import Nans
from delphi.epidata.acquisition.covidcast.csv_importer import CsvImporter
from delphi.utils.epiweek import delta_epiweeks

# py3tester coverage target
__test_target__ = 'delphi.epidata.acquisition.covidcast.csv_importer'


class UnitTests(unittest.TestCase):
  """Basic unit tests."""

  def test_is_sane_day(self):
    """Sanity check some dates."""

    self.assertTrue(CsvImporter.is_sane_day(20200418))

    self.assertFalse(CsvImporter.is_sane_day(22222222))
    self.assertFalse(CsvImporter.is_sane_day(20200001))
    self.assertFalse(CsvImporter.is_sane_day(20200199))
    self.assertFalse(CsvImporter.is_sane_day(202015))

  def test_is_sane_week(self):
    """Sanity check some weeks."""

    self.assertTrue(CsvImporter.is_sane_week(202015))

    self.assertFalse(CsvImporter.is_sane_week(222222))
    self.assertFalse(CsvImporter.is_sane_week(202000))
    self.assertFalse(CsvImporter.is_sane_week(202054))
    self.assertFalse(CsvImporter.is_sane_week(20200418))

  @patch("os.path.isdir")
  def test_find_issue_specific_csv_files(self,os_isdir_mock):
      """Recursively explore and find issue specific CSV files."""
      # check valid path
      path_prefix='prefix/to/the/data/issue_20200408'
      os_isdir_mock.return_value=True
      issue_path=path_prefix+'ght/20200408_state_rawsearch.csv'

      mock_glob = MagicMock()
      mock_glob.glob.side_effect = ([path_prefix], [issue_path])

      #check if the day is a valid day.
      issuedir_match= CsvImporter.PATTERN_ISSUE_DIR.match(path_prefix.lower())
      issue_date_value = int(issuedir_match.group(2))
      self.assertTrue(CsvImporter.is_sane_day(issue_date_value))

      found = set(CsvImporter.find_issue_specific_csv_files(path_prefix, glob=mock_glob))
      self.assertTrue(len(found)>0)

      # check unvalid path:
      path_prefix_invalid='invalid/prefix/to/the/data/issue_20200408'
      os_isdir_mock.return_value=False
      issue_path_invalid=path_prefix_invalid+'ght/20200408_state_rawsearch.csv'
      mock_glob_invalid = MagicMock()
      mock_glob_invalid.glob.side_effect = ([path_prefix_invalid], [issue_path_invalid])

      found = set(CsvImporter.find_issue_specific_csv_files(path_prefix_invalid, glob=mock_glob_invalid))
      self.assertFalse(len(found)>0)


  def test_find_csv_files(self):
    """Recursively explore and find CSV files."""

    path_prefix = 'prefix/to/the/data/'
    glob_paths = [
      # valid weekly
      path_prefix + 'fb_survey/weekly_202015_county_cli.csv',
      # valid daily
      path_prefix + 'ght/20200408_state_rawsearch.csv',
      # valid national
      path_prefix + 'valid/20200408_nation_sig.csv',
      # valid hhs
      path_prefix + 'valid/20200408_hhs_sig.csv',
      # invalid
      path_prefix + 'invalid/hello_world.csv',
      # invalid day
      path_prefix + 'invalid/22222222_b_c.csv',
      # invalid week
      path_prefix + 'invalid/weekly_222222_b_c.csv',
      # invalid geography
      path_prefix + 'invalid/20200418_province_c.csv',
      # ignored
      path_prefix + 'ignored/README.md',
    ]
    mock_glob = MagicMock()
    mock_glob.glob.return_value = glob_paths

    found = set(CsvImporter.find_csv_files(path_prefix, glob=mock_glob))

    expected_issue_day=int(date.today().strftime("%Y%m%d"))
    expected_issue_week=int(str(epi.Week.fromdate(date.today())))
    time_value_day = 20200408
    expected = set([
      (glob_paths[0], ('fb_survey', 'cli', 'week', 'county', 202015, expected_issue_week, delta_epiweeks(202015, expected_issue_week))),
      (glob_paths[1], ('ght', 'rawsearch', 'day', 'state', time_value_day, expected_issue_day, (date.today() - date(year=time_value_day // 10000, month=(time_value_day // 100) % 100, day=time_value_day % 100)).days)),
      (glob_paths[2], ('valid', 'sig', 'day', 'nation', time_value_day, expected_issue_day, (date.today() - date(year=time_value_day // 10000, month=(time_value_day // 100) % 100, day=time_value_day % 100)).days)),
      (glob_paths[3], ('valid', 'sig', 'day', 'hhs', time_value_day, expected_issue_day, (date.today() - date(year=time_value_day // 10000, month=(time_value_day // 100) % 100, day=time_value_day % 100)).days)),
      (glob_paths[4], None),
      (glob_paths[5], None),
      (glob_paths[6], None),
      (glob_paths[7], None),
    ])
    self.assertEqual(found, expected)

  def test_is_header_valid_allows_extra_columns(self):
    """Allow and ignore extra columns in the header."""

    columns = CsvImporter.REQUIRED_COLUMNS

    self.assertTrue(CsvImporter.is_header_valid(columns))
    self.assertTrue(CsvImporter.is_header_valid(columns | {'foo', 'bar'}))

  def test_is_header_valid_does_not_depend_on_column_order(self):
    """Allow columns to appear in any order."""

    # sorting changes the order of the columns
    columns = sorted(CsvImporter.REQUIRED_COLUMNS)

    self.assertTrue(CsvImporter.is_header_valid(columns))

  def test_floaty_int(self):
    """Parse ints that may look like floats."""

    self.assertEqual(CsvImporter.floaty_int('-1'), -1)
    self.assertEqual(CsvImporter.floaty_int('-1.0'), -1)

    with self.assertRaises(ValueError):
      CsvImporter.floaty_int('-1.1')

  def test_maybe_apply(self):
    """Apply a function to a value as long as it's not null-like."""

    self.assertEqual(CsvImporter.maybe_apply(float, '3.14'), 3.14)
    self.assertEqual(CsvImporter.maybe_apply(int, '1'), 1)
    self.assertIsNone(CsvImporter.maybe_apply(int, 'NA'))
    self.assertIsNone(CsvImporter.maybe_apply(int, 'NaN'))
    self.assertIsNone(CsvImporter.maybe_apply(float, ''))
    self.assertIsNone(CsvImporter.maybe_apply(float, None))

  def test_extract_and_check_row(self):
    """Apply various sanity checks to a row of data."""

    def make_row(
        geo_type='state',
        geo_id='vi',
        value='1.23',
        stderr='4.56',
        sample_size='100.5',
        missing_value=str(float(Nans.NOT_MISSING)),
        missing_stderr=str(float(Nans.NOT_MISSING)),
        missing_sample_size=str(float(Nans.NOT_MISSING))):
      row = MagicMock(
          geo_id=geo_id,
          value=value,
          stderr=stderr,
          sample_size=sample_size,
          missing_value=missing_value,
          missing_stderr=missing_stderr,
          missing_sample_size=missing_sample_size,
          spec=["geo_id", "value", "stderr", "sample_size",
                "missing_value", "missing_stderr", "missing_sample_size"])
      return geo_type, row

    # cases to test each failure mode
    failure_cases = [
      (make_row(geo_type='county', geo_id='1234'), 'geo_id'),
      (make_row(geo_type='county', geo_id='00000'), 'geo_id'),
      (make_row(geo_type='hrr', geo_id='600'), 'geo_id'),
      (make_row(geo_type='msa', geo_id='1234'), 'geo_id'),
      (make_row(geo_type='msa', geo_id='01234'), 'geo_id'),
      (make_row(geo_type='dma', geo_id='400'), 'geo_id'),
      (make_row(geo_type='state', geo_id='48'), 'geo_id'),
      (make_row(geo_type='state', geo_id='iowa'), 'geo_id'),
      (make_row(geo_type='nation', geo_id='0000'), 'geo_id'),
      (make_row(geo_type='hhs', geo_id='0'), 'geo_id'),
      (make_row(geo_type='province', geo_id='ab'), 'geo_type'),
      (make_row(stderr='-1'), 'stderr'),
      (make_row(geo_type=None), 'geo_type'),
      (make_row(geo_id=None), 'geo_id'),
      (make_row(value='inf'), 'value'),
      (make_row(stderr='inf'), 'stderr'),
      (make_row(sample_size='inf'), 'sample_size'),
      (make_row(geo_type='hrr', geo_id='hrr001'), 'geo_id'),
      (make_row(value='value'), 'value'),
      (make_row(stderr='stderr'), 'stderr'),
      (make_row(sample_size='sample_size'), 'sample_size'),
    ]

    for ((geo_type, row), field) in failure_cases:
      values, error = CsvImporter.extract_and_check_row(row, geo_type)
      self.assertIsNone(values)
      self.assertEqual(error, field)

    success_cases = [
      (make_row(), CsvImporter.RowValues('vi', 1.23, 4.56, 100.5, Nans.NOT_MISSING, Nans.NOT_MISSING, Nans.NOT_MISSING)),
      (make_row(value=None, stderr=np.nan, sample_size='', missing_value=str(float(Nans.DELETED)), missing_stderr=str(float(Nans.DELETED)), missing_sample_size=str(float(Nans.DELETED))), CsvImporter.RowValues('vi', None, None, None, Nans.DELETED, Nans.DELETED, Nans.DELETED)),
      (make_row(stderr='', sample_size='NA', missing_stderr=str(float(Nans.OTHER)), missing_sample_size=str(float(Nans.OTHER))), CsvImporter.RowValues('vi', 1.23, None, None, Nans.NOT_MISSING, Nans.OTHER, Nans.OTHER)),
      (make_row(sample_size=None, missing_value='missing_value', missing_stderr=str(float(Nans.OTHER)), missing_sample_size=str(float(Nans.NOT_MISSING))), CsvImporter.RowValues('vi', 1.23, 4.56, None, Nans.NOT_MISSING, Nans.NOT_MISSING, Nans.OTHER)),
    ]

    for ((geo_type, row), field) in success_cases:
      values, error = CsvImporter.extract_and_check_row(row, geo_type)
      self.assertIsNone(error)
      self.assertIsInstance(values, CsvImporter.RowValues)
      self.assertEqual(values.geo_value, field.geo_value)
      self.assertEqual(values.value, field.value)
      self.assertEqual(values.stderr, field.stderr)
      self.assertEqual(values.sample_size, field.sample_size)

  def test_load_csv_with_invalid_header(self):
    """Bail loading a CSV when the header is invalid."""

    data = {'foo': [1, 2, 3]}
    mock_pandas = MagicMock()
    mock_pandas.read_csv.return_value = pandas.DataFrame(data=data)
    filepath = 'path/name.csv'
    geo_type = 'state'

    rows = list(CsvImporter.load_csv(filepath, geo_type, pandas=mock_pandas))

    self.assertTrue(mock_pandas.read_csv.called)
    self.assertTrue(mock_pandas.read_csv.call_args[0][0], filepath)
    self.assertEqual(rows, [None])

  def test_load_csv_with_valid_header(self):
    """Yield sanity checked `RowValues` from a valid CSV file."""

    # one invalid geo_id, but otherwise valid
    data = {
      'geo_id': ['ca', 'tx', 'fl', '123'],
      'val': ['1.1', '1.2', '1.3', '1.4'],
      'se': ['2.1', '2.2', '2.3', '2.4'],
      'sample_size': ['301', '302', '303', '304'],
    }
    mock_pandas = MagicMock()
    mock_pandas.read_csv.return_value = pandas.DataFrame(data=data)
    filepath = 'path/name.csv'
    geo_type = 'state'

    rows = list(CsvImporter.load_csv(filepath, geo_type, pandas=mock_pandas))

    self.assertTrue(mock_pandas.read_csv.called)
    self.assertTrue(mock_pandas.read_csv.call_args[0][0], filepath)
    self.assertEqual(len(rows), 4)

    self.assertEqual(rows[0].geo_value, 'ca')
    self.assertEqual(rows[0].value, 1.1)
    self.assertEqual(rows[0].stderr, 2.1)
    self.assertEqual(rows[0].sample_size, 301)

    self.assertEqual(rows[1].geo_value, 'tx')
    self.assertEqual(rows[1].value, 1.2)
    self.assertEqual(rows[1].stderr, 2.2)
    self.assertEqual(rows[1].sample_size, 302)

    self.assertEqual(rows[2].geo_value, 'fl')
    self.assertEqual(rows[2].value, 1.3)
    self.assertEqual(rows[2].stderr, 2.3)
    self.assertEqual(rows[2].sample_size, 303)

    self.assertIsNone(rows[3])

    # now with missing values!
    data = {
      'geo_id': ['ca', 'tx', 'fl', 'ak', 'wa'],
      'val': [np.nan, '1.2', '1.3', '1.4', '1.5'],
      'se': ['2.1', "na", '2.3', '2.4', '2.5'],
      'sample_size': ['301', '302', None, '304', None],
      'missing_value': [Nans.NOT_APPLICABLE] + [Nans.NOT_MISSING] * 3 + [None],
      'missing_stderr': [Nans.NOT_MISSING, Nans.REGION_EXCEPTION, Nans.NOT_MISSING, Nans.NOT_MISSING] + [None],
      'missing_sample_size': [Nans.NOT_MISSING] * 2 + [Nans.REGION_EXCEPTION] * 2 + [None]
    }
    mock_pandas = MagicMock()
    mock_pandas.read_csv.return_value = pandas.DataFrame(data=data)
    filepath = 'path/name.csv'
    geo_type = 'state'

    rows = list(CsvImporter.load_csv(filepath, geo_type, pandas=mock_pandas))

    self.assertTrue(mock_pandas.read_csv.called)
    self.assertTrue(mock_pandas.read_csv.call_args[0][0], filepath)
    self.assertEqual(len(rows), 5)

    self.assertEqual(rows[0].geo_value, 'ca')
    self.assertIsNone(rows[0].value)
    self.assertEqual(rows[0].stderr, 2.1)
    self.assertEqual(rows[0].sample_size, 301)
    self.assertEqual(rows[0].missing_value, Nans.NOT_APPLICABLE)
    self.assertEqual(rows[0].missing_stderr, Nans.NOT_MISSING)
    self.assertEqual(rows[0].missing_sample_size, Nans.NOT_MISSING)

    self.assertEqual(rows[1].geo_value, 'tx')
    self.assertEqual(rows[1].value, 1.2)
    self.assertIsNone(rows[1].stderr)
    self.assertEqual(rows[1].sample_size, 302)
    self.assertEqual(rows[1].missing_value, Nans.NOT_MISSING)
    self.assertEqual(rows[1].missing_stderr, Nans.REGION_EXCEPTION)
    self.assertEqual(rows[1].missing_sample_size, Nans.NOT_MISSING)

    self.assertEqual(rows[2].geo_value, 'fl')
    self.assertEqual(rows[2].value, 1.3)
    self.assertEqual(rows[2].stderr, 2.3)
    self.assertIsNone(rows[2].sample_size)
    self.assertEqual(rows[2].missing_value, Nans.NOT_MISSING)
    self.assertEqual(rows[2].missing_stderr, Nans.NOT_MISSING)
    self.assertEqual(rows[2].missing_sample_size, Nans.REGION_EXCEPTION)

    self.assertEqual(rows[3].geo_value, 'ak')
    self.assertEqual(rows[3].value, 1.4)
    self.assertEqual(rows[3].stderr, 2.4)
    self.assertEqual(rows[3].sample_size, 304)
    self.assertEqual(rows[3].missing_value, Nans.NOT_MISSING)
    self.assertEqual(rows[3].missing_stderr, Nans.NOT_MISSING)
    self.assertEqual(rows[3].missing_sample_size, Nans.NOT_MISSING)

    self.assertEqual(rows[4].geo_value, 'wa')
    self.assertEqual(rows[4].value, 1.5)
    self.assertEqual(rows[4].stderr, 2.5)
    self.assertEqual(rows[4].sample_size, None)
    self.assertEqual(rows[4].missing_value, Nans.NOT_MISSING)
    self.assertEqual(rows[4].missing_stderr, Nans.NOT_MISSING)
    self.assertEqual(rows[4].missing_sample_size, Nans.OTHER)