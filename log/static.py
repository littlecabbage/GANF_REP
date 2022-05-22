

def get_metrics(file_name):
    rst_list =[]

    f1_list = []
    pre_list = []
    rec_list = []


    with open(file_name, "r") as f:
        lines = f.readlines()
        for l in lines:
            if l.startswith("[Best"):
                rst_list.append(l)


    for item in rst_list:
        left = item.split("{")
        right = [x.split("}") for x in left]
        # right = [x[0] for x in right]
        num = [x[0] for x in right][2:]
        f1 = num[0]
        pre = num[1]
        rec = num[2]

        f1_list.append((f1, pre, rec))
        # pre_list.append(pre)
        # rec_list.append(rec)
        # print(f1, pre, rec)

    return f1_list# , pre_list, rec_list


if __name__ == "__main__":


    # f1_list = get_metrics("3-1.log")

    # # f1_list.sort(key = lambda x: x[0])

    # for beta in [3, 5]:
    #     for times in range(1,6):
    #         file_name = f"{beta}-{times}.log"
    #         f1_list = get_metrics(file_name)
    #         sorted(f1_list, key=lambda x: x[0])
    #         print(file_name, f1_list[0])


    f1_list = get_metrics("0-0.log")
    sorted(f1_list, key=lambda x: x[0])
    print("full_data_water.log", f1_list[0])

    



    
