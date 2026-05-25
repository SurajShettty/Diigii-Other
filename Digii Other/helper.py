import pymysql

def connect_to_tenant_database(tenant_name):
    conn = pymysql.connect(
        host="collpolldb11-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="suraj_shetty",
        password="pTXr8yJmOR",
        database="collpoll_gdgu"
    )

# def connect_to_tenant_database(tenant_name):
#     conn = pymysql.connect(
#         host="digiidb3-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
#         user="suraj_shetty",
#         password="AdaQwNaEPo",
#         database="collpoll_isbr"
#     )
    return conn