n = int(input())

bt = list(map(int, input().split()))
qt = int(input())

rt = bt[:]
t = 0

wt = [0]*n
tat = [0]*n

done = 0

while True:
    flag = True

    i = 0
    while i < n:
        if rt[i] > 0:
            flag = False

            if rt[i] > qt:
                t += qt
                rt[i] -= qt
            else:
                t += rt[i]
                wt[i] = t - bt[i]
                rt[i] = 0
                done += 1

        i += 1

    if flag:
        break


j = 0
while j < n:
    tat[j] = bt[j] + wt[j]
    j += 1


i = 0
while i < n:
    print("P"+str(i), wt[i], tat[i])
    i += 1


print("avg wt:", sum(wt)/n)
print("avg tat:", sum(tat)/n)