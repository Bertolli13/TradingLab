import yfinance as yf


df = yf.download(
    "NQ=F",
    period="7d",
    interval="1m",
    auto_adjust=False,
    prepost=True,
    progress=False
)

print("\nPRIMEIRAS LINHAS")
print(df.head())

print("\nÚLTIMAS LINHAS")
print(df.tail())

print("\nTOTAL DE LINHAS")
print(len(df))

print("\nINÍCIO")
print(df.index.min())

print("\nFIM")
print(df.index.max())

print("\nCOLUNAS")
print(df.columns)