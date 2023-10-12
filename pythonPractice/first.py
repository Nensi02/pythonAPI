class Solution:
    def record(self, a):
        num_list = anser = []
        str_list = []
        sorting_list = []
        if len(a) >= 1 and len(a) <= 1000:
            for sub_data in a:
                if len(sub_data) >= 3 and len(sub_data) <= 1000:
                    sub_list = sub_data.split("-")
                    first_pos = sub_list.pop(0)
                    final_str = ("-".join(sub_list)) + '-' + first_pos
                    print(final_str)
                    if sub_list[1].isnumeric():
                        num_list.append(final_str)
                    else:
                        str_list.append(final_str)
            anser = sorted(str_list) + sorted(num_list)

            for j in anser:
                sub_lis = j.split("-")
                last_pos = sub_lis.pop()
                final_strs = last_pos + "-" + ("-".join(sub_lis))
                sorting_list.append(final_strs)

            print(sorting_list)

# a = ["dig1-8-1-5-1", "let1-art-can", "dig2-3-6", "let2-own-kit-dig", "let3-art-zero"]
a= ["zr8-dhhlswshxcs", "wv7-hrj-oh-fs", "ma1-kihkolgrtu", "qn1-xkesdlghfusw", "dj9-7-6-9-0-5", "zp1-2-6-9-5-8-5", "fz9-r-snlgjy", "il3-0-9-4-6-4-8", "uk7-yh-tic-slj", "mf2-8-2-7-9-7-6", "aw0-wbipdtvvut"]
inst = Solution()
inst.record(a)