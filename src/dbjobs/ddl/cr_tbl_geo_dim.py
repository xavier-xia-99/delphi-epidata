# *******************************************************************************************************
# cr_tbl_geo_dim.py
# *******************************************************************************************************
# *******************************************************************************************************
# Command to be run

command = '''
CREATE TABLE <param1>.geo_dim (
        `geo_key_id` BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
        `geo_type` varchar(12),
        `geo_value` varchar(12),
        `compressed_geo_key` varchar(100),
        PRIMARY KEY (`geo_key_id`) USING BTREE,
        unique INDEX `compressed_geo_key_ind` (`compressed_geo_key`) USING BTREE)
'''

usage = '''
Usage:  --target=<db_alias> --param1=<schema>
'''

params = '''
param1=prompt target=prompt
'''

# *******************************************************************************************************
# End
# *******************************************************************************************************
