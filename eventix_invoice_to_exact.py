import pandas as pd
import tabula
from datetime import datetime
import json
import os
import shutil


def eur_to_float(eur_value):
    return float(eur_value.split("€ ")[1].replace(",", "."))


def get_entry_date(weeknr, year):
    weeknr = str(weeknr)
    year = str(year)
    if len(weeknr) == 1:
        weeknr = f"0{weeknr}"
    d = f"{year}-W{weeknr}"
    r = datetime.strptime(d + '-1', "%Y-W%W-%w")
    r = r.strftime("%d-%m-%Y")
    return r


def get_files():
    path = os.getcwd()
    files = []
    files_dict = []
    for file in os.listdir(path):
        if file.endswith(".pdf") or file.endswith(".PDF"):
            files.append(file)
    for i in files:
        try:
            weeknr = str(datetime.strptime(i[:10], "%Y-%m-%d").isocalendar()[1] -1)
            year = i[:4]
            invoice = i.split()[1]
            if len(weeknr) == 1:
                weeknr = f"0{weeknr}"
            files_dict.append({"filename":i, "weeknr": weeknr, "year": year, "invoice": invoice})
        except:
            pass
    return files_dict


def get_cost_center(description):
    if description.count("(") > 1:
        description = description.replace("(", "", description.count("(") - 1)
    name = description.split("Event: ")[1].split(" (")[0].lower()
    date = description.split("(")[1].split(")")[0].replace("-", "").split(" ")[0][3:]
    cost_center = date + name[:3]
    try:
        int(cost_center[:5])
        return cost_center
    except:
        return


def get_settings(settings_name= "settings.json"):
    with open(settings_name) as json_file:
        settings = json.load(json_file)
    return settings


def clean_df(df, df_sort=""):
    if df_sort == "ticket":
        df["cost_center"] = df["description"].apply(lambda x: get_cost_center(x)) #makes a column for the cost center from the values in the column description
        df["event_date"] = df["description"].apply(lambda x: datetime.strptime(x.split("(")[-1], '%Y-%m-%d %H:%M)')) #makes a column for the event date from the values in the column description
        df["description"] = df["description"].apply(lambda x: x.split(" (")[0].split("Event: ")[1]) #removes "Event: " and the date from the description
        df["ticketsoort"] = df["ticketsoort"].apply(lambda x: x.split("Ticket: ")[1])
    df["sold_tickets"] = df["sold_tickets"].apply(lambda x: int(x)) #makes an int from the string

    eur_to_float_list = ["ticket_price", "tickets_total", "servicefee_ticket", "servicefee_total", "total"]
    for i in range(len(eur_to_float_list)):
        df[eur_to_float_list[i]] = df[eur_to_float_list[i]].apply(lambda x: float(x.split("€ ")[1].replace(",", ".")))#removes the € sign and replace the comma with a dot and makes it a float
    return df


def make_exact_csv(df, entry_date, weeknr, year, paymentcosts, directory, invoice): 
    settings = get_settings()
    exact_dict = []
    tickets_total = df["tickets_total"].sum()
    servicefee_total = df["servicefee_total"].sum()
    print(servicefee_total, type(servicefee_total))
    
    #Total from suspense account
    ticketstotal = {
            "Boekdatum": entry_date, 
            "GLAccount": settings["gbrkincome"],
            "VATCode": settings["btw_zero_code"],
            "Description":f'week {weeknr} ticket en servicekosten - {invoice}', 
            "AmountFC": round(float(tickets_total + servicefee_total + paymentcosts) * -1, 2)
            }
    exact_dict.append(ticketstotal)
        
    for index, row in df.iterrows(): 
        
        tickets_total = float(row["tickets_total"])
        tickets_total_vat = round(tickets_total * settings["vat_low_perc"], 2) 
        ticket_dict_val = round((tickets_total - tickets_total_vat), 2)
        serv_total = float(row["servicefee_total"])
        serv_total_vat = round(serv_total * settings["vat_low_perc"], 2)


        ticket_dict = {  #for ticket for event
            "GLAccount": settings["gbrkticket"],
            "Description":f'week {weeknr}-ticket-{row["description"][:17]}-202{row["cost_center"][:5]}-{row["sold_tickets"]}-{row["ticketsoort"][:8]}', 
            "VATCode": settings["btw_zero_code"], 
            "CostCenter": row["cost_center"],
            "AmountFC": ticket_dict_val
            }
        exact_dict.append(ticket_dict)
        
        service_dict = {  #for servicecost for event
            "GLAccount": settings["gbrkservice"],
            "Description":f'week {weeknr}-serv-{row["description"][:17]}-202{row["cost_center"][:5]}-{row["sold_tickets"]}-{row["ticketsoort"][:8]}', 
            "VATCode": settings["btw_zero_code"]
            "CostCenter": row["cost_center"],
            "AmountFC": round((serv_total - serv_total_vat), 2)
            }
        exact_dict.append(service_dict)

    tickets_total = df["tickets_total"].sum()
    servicefee_total = df["servicefee_total"].sum()
    vat = round(float(tickets_total + servicefee_total) * settings["vat_low_perc"], 2)

    ticket_service_btw = {  #total vat for ticket and service
        "GLAccount": settings["gbrkbtw_low"],
        "VATCode": settings["btw_low_code_excl"],
        "Description":f'week {weeknr} ticket en servicekosten btw', 
        "AmountFC": vat
        }
    exact_dict.append(ticket_service_btw)


    ##### PAYMENTPROVIDERS
    """
    paymenta = {
            "GLAccount": settings["gbrkservice"],
            "VATCode": settings["btw_zero_code"],
            "Description":f'week {weeknr} kosten payment provider', 
            "AmountFC": round(float(paymentcosts) * -1, 2)
            }
    
    exact_dict.append(paymenta)

    paymenta_vat = {
            "GLAccount": settings["gbrkbtw_zero"],
            "VATCode": settings["btw_zero_code"],
            "Description":f'week {weeknr} kosten payment provider btw', 
            "AmountFC": round(0, 2)
            }

    exact_dict.append(paymenta_vat)
    """
    paymentb = {
            "GLAccount": settings["gbrkservpay"],
            "VATCode": settings["btw_zero_code"],
            "AmountVATFC": 0,
            "Description":f'week {weeknr} kosten payment provider', 
            "AmountFC": round(float(paymentcosts), 2)
            }

    exact_dict.append(paymentb)

    
    df = pd.DataFrame(exact_dict)
    df["AmountFC"] = df["AmountFC"].apply(lambda x: float(x) * -1)

    difference = round(df["AmountFC"].sum(),2)
    if  0 < abs(difference) < 1:
        df["AmountFC"].replace(vat * -1, (vat + difference) * -1, inplace=True)

    #standard rules
    df["Regel"] = 1
    df["Boekdatum"] = entry_date
    df["Journal"] = settings["journal"]
    df["Year"] = year
    df["Period"] = entry_date[3:5]

    df = df[["Regel", "Journal", "Year", "Period", "Boekdatum", "GLAccount", "Description", "CostCenter", "VATCode", "AmountFC", "AmountVATFC"]]
    print(df)
    difference = round(df["AmountFC"].sum(),2)
    print("difference:", difference)
    if abs(difference) < 1:
        df.to_csv(f"{directory}memoriaal eventix {weeknr}-{year}.csv", index=False, header=False)
        df.to_excel(f"{directory} xlsx memoriaal eventix {weeknr}-{year}.xlsx", index=False)
    else:
        print("Error, verschil te groot om te boeken")
        from time import sleep
        sleep(5000)

    
def main():
    files = get_files()
    for i in files:
        filename = i["filename"]
        weeknr = i["weeknr"]
        year = i["year"]
        invoice = i["invoice"]
        print(filename, weeknr, year)

        entry_date = get_entry_date(weeknr, year)
        directory = f"data/{year}/{year}-{weeknr}/"
        if not os.path.exists(directory):
            os.makedirs(directory)

        df = tabula.read_pdf(filename, pages="all", multiple_tables=False) #makes a list of dataframes from the pdf
        df = df[0] #takes the first df in the list of dfs
        df = df.rename(columns={"Product": "ticketsoort", "Description": "description", "Amount": "sold_tickets", "Price/Product": "ticket_price", "Product Total": "tickets_total", "Kickback": "servicefee_ticket", "Kickbacks Total": "servicefee_total", "Total": "total"})

        costs_df = df.loc[df.ticketsoort.isin(["PayPal", "Podiumcadeaukaart", "CreditCard", "Bancontact"])]
        tickets_df = df.loc[df.ticketsoort.str.startswith("Ticket")].reset_index(drop=True) #only gets the products that starts with the word ticket

        tickets_df = clean_df(tickets_df, "ticket")
        costs_df = clean_df(costs_df)
    
        print(costs_df)
        print(tickets_df)
        total_tickets = round(tickets_df["total"].sum(), 2)
        total_costs = round(costs_df["total"].sum(), 2)
        total = total_tickets + total_costs

        print("Ticketverkoop:", total_tickets)
        print("Servicekosten:", total_costs)
        print("Totaal:", total)

        tickets_df.to_csv(f"{directory}tickets {weeknr}-{year}_df.csv")
        make_exact_csv(tickets_df, entry_date, weeknr, year, total_costs, directory, invoice)
        shutil.move(filename, f"{directory}{filename}")


if __name__ == "__main__":
    main()
